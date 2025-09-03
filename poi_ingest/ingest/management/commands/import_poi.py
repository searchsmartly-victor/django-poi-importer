"""
Management command to import POI data from various file formats.

Usage:
    python manage.py import_poi <path ...>
    python manage.py import_poi data/*.csv --dry-run
    python manage.py import_poi data/ --batch-size 100 --verbose
"""

import glob
import logging
import time
from pathlib import Path
from typing import Dict, List, Any, Iterator

from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction

from ingest.services.parsers import parse_csv, parse_json, parse_xml
from ingest.services.upsert import upsert_poi, validate_poi_payload

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Management command to import POI data from files.
    """

    help = "Import POI data from CSV, JSON, or XML files"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stats = {
            "files_seen": 0,
            "files_processed": 0,
            "files_skipped": 0,
            "records_ok": 0,
            "records_skipped": 0,
            "created": 0,
            "updated": 0,
            "errors": 0,
        }
        self.start_time = None
        self.dry_run = False
        self.batch_size = 1000
        self.stop_on_error = False
        self.verbose = False

    def add_arguments(self, parser: CommandParser) -> None:
        """
        Add command line arguments.
        """
        parser.add_argument(
            "paths",
            nargs="+",
            type=str,
            help="File paths, directory paths, or glob patterns to import",
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Parse and validate only, do not save to database",
        )

        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="Number of records to process in each transaction batch",
        )

        parser.add_argument(
            "--stop-on-error",
            action="store_true",
            default=False,
            help="Stop processing on first error instead of continuing",
        )

        parser.add_argument(
            "--verbose",
            action="store_true",
            default=False,
            help="Enable verbose debug logging",
        )

    def handle(self, *args, **options) -> None:
        """
        Main command handler.
        """
        self.start_time = time.time()
        self.dry_run = options["dry_run"]
        self.batch_size = options["batch_size"]
        self.stop_on_error = options["stop_on_error"]
        self.verbose = options["verbose"]

        # Configure logging level
        if self.verbose:
            logging.getLogger("ingest").setLevel(logging.DEBUG)
            self.stdout.write("Verbose logging enabled")

        if self.dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No data will be saved")
            )

        # Discover all files to process
        files_to_process = self._discover_files(options["paths"])

        if not files_to_process:
            self.stdout.write(self.style.ERROR("No files found to process"))
            return

        self.stdout.write(f"Found {len(files_to_process)} files to process")

        # Process each file
        for file_path in files_to_process:
            try:
                self._process_file(file_path)
            except Exception as e:
                self.stats["errors"] += 1
                logger.error(f"Fatal error processing file {file_path}: {e}")
                if self.stop_on_error:
                    self.stdout.write(self.style.ERROR(f"Stopping on error: {e}"))
                    break
                else:
                    self.stdout.write(
                        self.style.ERROR(f"Error processing {file_path}: {e}")
                    )

        # Print summary
        self._print_summary()

    def _discover_files(self, paths: List[str]) -> List[Path]:
        """
        Discover all files to process from paths and globs.
        """
        files_to_process = []

        for path_str in paths:
            path = Path(path_str)

            # Handle glob patterns
            if "*" in path_str or "?" in path_str:
                glob_files = glob.glob(path_str, recursive=True)
                for glob_file in glob_files:
                    file_path = Path(glob_file)
                    if file_path.is_file():
                        files_to_process.append(file_path)
                        self.stats["files_seen"] += 1

            # Handle single file
            elif path.is_file():
                files_to_process.append(path)
                self.stats["files_seen"] += 1

            # Handle directory (recurse)
            elif path.is_dir():
                for file_path in path.rglob("*"):
                    if file_path.is_file():
                        files_to_process.append(file_path)
                        self.stats["files_seen"] += 1

            else:
                self.stdout.write(self.style.WARNING(f"Path not found: {path_str}"))

        # Filter by supported extensions
        supported_files = []
        for file_path in files_to_process:
            ext = file_path.suffix.lower()
            if ext in [".csv", ".json", ".xml"]:
                supported_files.append(file_path)
            else:
                self.stats["files_skipped"] += 1
                logger.info(f"Skipping unsupported file type: {file_path}")

        return supported_files

    def _process_file(self, file_path: Path) -> None:
        """
        Process a single file based on its extension.
        """
        self.stdout.write(f"Processing: {file_path}")

        ext = file_path.suffix.lower()

        # Select appropriate parser
        if ext == ".csv":
            parser = parse_csv
        elif ext == ".json":
            parser = self._stream_parse_json
        elif ext == ".xml":
            parser = parse_xml
        else:
            self.stats["files_skipped"] += 1
            logger.info(f"Unsupported file type: {ext}")
            return

        try:
            # Stream parse the file
            records_iterator = parser(file_path)

            # Process in batches
            batch = []

            for record in records_iterator:
                # Validate record
                validation_errors = validate_poi_payload(record)
                if validation_errors:
                    self.stats["records_skipped"] += 1
                    logger.warning(
                        f"Skipping invalid record in {file_path}: "
                        f"external_id={record.get('external_id')}, "
                        f"errors={validation_errors}"
                    )
                    if self.stop_on_error:
                        raise ValueError(f"Validation errors: {validation_errors}")
                    continue

                self.stats["records_ok"] += 1

                if not self.dry_run:
                    batch.append(record)

                    # Process batch when full
                    if len(batch) >= self.batch_size:
                        self._process_batch(batch, file_path)
                        batch = []

                if self.verbose and self.stats["records_ok"] % 100 == 0:
                    self.stdout.write(
                        f"Processed {self.stats['records_ok']} records..."
                    )

            # Process remaining records in batch
            if batch and not self.dry_run:
                self._process_batch(batch, file_path)

            self.stats["files_processed"] += 1

        except Exception as e:
            self.stats["files_skipped"] += 1
            logger.error(f"Error processing file {file_path}: {e}")
            if self.stop_on_error:
                raise

    def _stream_parse_json(self, file_path: Path) -> Iterator[Dict[str, Any]]:
        """
        Stream parse JSON files to handle large files efficiently.
        """
        try:
            # Try to use ijson for streaming large JSON arrays
            try:
                import ijson

                with open(file_path, "rb") as f:
                    # Try to parse as array of objects
                    try:
                        parser = ijson.items(f, "item")
                        for obj in parser:
                            if isinstance(obj, dict):
                                yield obj
                        return
                    except (ijson.JSONError, ValueError):
                        # Reset file pointer and fallback
                        f.seek(0)
            except ImportError:
                logger.info("ijson not available, using standard JSON parsing")

            # Fallback to regular JSON parsing
            for record in parse_json(file_path):
                yield record

        except Exception as e:
            logger.error(f"Error in JSON streaming for {file_path}: {e}")
            raise

    def _process_batch(self, batch: List[Dict[str, Any]], file_path: Path) -> None:
        """
        Process a batch of records in a transaction.
        """
        try:
            with transaction.atomic():
                for record in batch:
                    try:
                        poi, created = upsert_poi(record)

                        if created:
                            self.stats["created"] += 1
                        else:
                            self.stats["updated"] += 1

                    except Exception as e:
                        self.stats["errors"] += 1
                        logger.error(
                            f"Error upserting record from {file_path}: "
                            f"external_id={record.get('external_id')}, error={e}"
                        )
                        if self.stop_on_error:
                            raise

        except Exception as e:
            # If batch fails, try individual records
            logger.warning(
                f"Batch failed for {file_path}, trying individual records: {e}"
            )

            for record in batch:
                try:
                    poi, created = upsert_poi(record)

                    if created:
                        self.stats["created"] += 1
                    else:
                        self.stats["updated"] += 1

                except Exception as e:
                    self.stats["errors"] += 1
                    logger.error(
                        f"Error upserting individual record: "
                        f"external_id={record.get('external_id')}, error={e}"
                    )
                    if self.stop_on_error:
                        raise

    def _print_summary(self) -> None:
        """
        Print a formatted summary table of the import operation.
        """
        duration = time.time() - self.start_time

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("POI IMPORT SUMMARY"))
        self.stdout.write("=" * 60)

        # File statistics
        self.stdout.write(f"Files seen:       {self.stats['files_seen']}")
        self.stdout.write(f"Files processed:  {self.stats['files_processed']}")
        self.stdout.write(f"Files skipped:    {self.stats['files_skipped']}")

        # Record statistics
        self.stdout.write(f"\nRecords parsed:   {self.stats['records_ok']}")
        self.stdout.write(f"Records skipped:  {self.stats['records_skipped']}")

        if not self.dry_run:
            # Database operations
            self.stdout.write(f"\nPOIs created:     {self.stats['created']}")
            self.stdout.write(f"POIs updated:     {self.stats['updated']}")
            self.stdout.write(f"Errors:           {self.stats['errors']}")

            # Success rate
            total_attempted = (
                self.stats["created"] + self.stats["updated"] + self.stats["errors"]
            )
            if total_attempted > 0:
                success_rate = (
                    (self.stats["created"] + self.stats["updated"]) / total_attempted
                ) * 100
                self.stdout.write(f"Success rate:     {success_rate:.1f}%")
        else:
            self.stdout.write(
                f"\n{self.style.WARNING('DRY RUN - No database changes made')}"
            )

        # Performance
        self.stdout.write(f"\nDuration:         {duration:.2f} seconds")
        if self.stats["records_ok"] > 0:
            rate = self.stats["records_ok"] / duration
            self.stdout.write(f"Processing rate:  {rate:.1f} records/second")

        self.stdout.write("=" * 60)

        # Final status
        if self.stats["errors"] > 0:
            self.stdout.write(
                self.style.WARNING(
                    f"Import completed with {self.stats['errors']} errors. "
                    "Check logs for details."
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS("Import completed successfully!"))
