"""
Tests for management command CLI functionality.
"""

import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from ingest.models import PointOfInterest


class TestCLIOptions(TestCase):
    """Test management command CLI options."""

    def test_cli_dry_run_does_not_persist(self):
        """Test that --dry-run does not persist data to database."""
        csv_content = """poi_id,poi_name,poi_category,poi_latitude,poi_longitude,poi_ratings
dry_run_001,Dry Run Restaurant,restaurant,40.7128,-74.0060,"{4.5,3.8,4.2}"
dry_run_002,Dry Run Hotel,hotel,40.7589,-73.9851,"{3.5,4.0,2.8}"
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            f.flush()

            # Count POIs before dry run
            initial_count = PointOfInterest.objects.count()

            # Run import with --dry-run
            out = StringIO()
            call_command("import_poi", f.name, "--dry-run", stdout=out)

            # Verify no POIs were created
            final_count = PointOfInterest.objects.count()
            self.assertEqual(initial_count, final_count)

            # Verify dry run message in output
            output = out.getvalue()
            self.assertIn("DRY RUN", output)
            self.assertIn("No database changes made", output)

        Path(f.name).unlink()

    def test_cli_stop_on_error_aborts(self):
        """Test that --stop-on-error aborts on first bad row."""
        # Create CSV with good row followed by bad row
        csv_content = """poi_id,poi_name,poi_category,poi_latitude,poi_longitude,poi_ratings
good_001,Good Restaurant,restaurant,40.7128,-74.0060,"{4.5,3.8,4.2}"
,Bad Row Missing ID,restaurant,40.7589,-73.9851,"{3.5,4.0}"
good_003,Should Not Process,restaurant,40.7794,-73.9632,"{4.8,4.9}"
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            f.flush()

            initial_count = PointOfInterest.objects.count()

            # Run import with --stop-on-error (should fail)
            out = StringIO()
            err = StringIO()

            # Command should exit with error
            with self.assertRaises((SystemExit, Exception)):
                call_command(
                    "import_poi", f.name, "--stop-on-error", stdout=out, stderr=err
                )

            # Should have processed at most the first record before stopping
            final_count = PointOfInterest.objects.count()
            records_created = final_count - initial_count
            self.assertLessEqual(records_created, 1)  # At most 1 record processed

        Path(f.name).unlink()

    def test_cli_batch_size_option(self):
        """Test that --batch-size option works correctly."""
        csv_content = """poi_id,poi_name,poi_category,poi_latitude,poi_longitude,poi_ratings
batch_001,Batch Restaurant 1,restaurant,40.7128,-74.0060,"{4.5,3.8}"
batch_002,Batch Restaurant 2,restaurant,40.7589,-73.9851,"{3.5,4.0}"
batch_003,Batch Restaurant 3,restaurant,40.7794,-73.9632,"{4.8,4.9}"
batch_004,Batch Restaurant 4,restaurant,40.7000,-74.0000,"{4.0,4.5}"
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            f.flush()

            initial_count = PointOfInterest.objects.count()

            # Run import with small batch size
            out = StringIO()
            call_command("import_poi", f.name, "--batch-size", "2", stdout=out)

            # Verify all records were imported despite small batch size
            final_count = PointOfInterest.objects.count()
            self.assertEqual(final_count - initial_count, 4)

            # Verify output shows completion
            output = out.getvalue()
            self.assertIn("Import completed successfully", output)

        Path(f.name).unlink()

    def test_cli_verbose_option(self):
        """Test that --verbose option provides detailed logging."""
        csv_content = """poi_id,poi_name,poi_category,poi_latitude,poi_longitude,poi_ratings
verbose_001,Verbose Test Restaurant,restaurant,40.7128,-74.0060,"{4.5,3.8}"
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            f.flush()

            # Run import with --verbose
            out = StringIO()
            call_command("import_poi", f.name, "--verbose", stdout=out)

            output = out.getvalue()

            # Verify verbose output contains expected messages
            self.assertIn("Verbose logging enabled", output)
            self.assertIn("Processing:", output)

        Path(f.name).unlink()

    def test_cli_multiple_files(self):
        """Test CLI with multiple file arguments."""
        # Create two CSV files
        csv_content1 = """poi_id,poi_name,poi_category,poi_latitude,poi_longitude,poi_ratings
multi_001,Multi File Restaurant 1,restaurant,40.7128,-74.0060,"{4.5,3.8}"
"""

        csv_content2 = """poi_id,poi_name,poi_category,poi_latitude,poi_longitude,poi_ratings
multi_002,Multi File Restaurant 2,restaurant,40.7589,-73.9851,"{3.5,4.0}"
"""

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as f1, tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as f2:

            f1.write(csv_content1)
            f1.flush()
            f2.write(csv_content2)
            f2.flush()

            initial_count = PointOfInterest.objects.count()

            # Run import with multiple files
            out = StringIO()
            call_command("import_poi", f1.name, f2.name, stdout=out)

            # Verify both files were processed
            final_count = PointOfInterest.objects.count()
            self.assertEqual(final_count - initial_count, 2)

            output = out.getvalue()
            self.assertIn("Found 2 files to process", output)

        Path(f1.name).unlink()
        Path(f2.name).unlink()
