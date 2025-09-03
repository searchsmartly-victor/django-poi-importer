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
    
    def test_dry_run_does_not_persist(self):
        """Test that --dry-run does not persist data to database."""
        csv_content = """poi_id,poi_name,poi_category,poi_latitude,poi_longitude,poi_ratings
dry_run_001,Dry Run Restaurant,restaurant,40.7128,-74.0060,"{4.5,3.8,4.2}"
dry_run_002,Dry Run Hotel,hotel,40.7589,-73.9851,"{3.5,4.0,2.8}"
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            f.flush()
            
            # Count POIs before dry run
            initial_count = PointOfInterest.objects.count()
            
            # Run import with --dry-run
            out = StringIO()
            call_command('import_poi', f.name, '--dry-run', stdout=out)
            
            # Verify no POIs were created
            final_count = PointOfInterest.objects.count()
            self.assertEqual(initial_count, final_count)
            
            # Verify dry run message in output
            output = out.getvalue()
            self.assertIn('DRY RUN', output)
            self.assertIn('No database changes made', output)
            
        Path(f.name).unlink()
    
    def test_stop_on_error_aborts_on_bad_row(self):
        """Test that --stop-on-error aborts processing on first error."""
        # Create CSV with one good row and one bad row
        csv_content = """poi_id,poi_name,poi_category,poi_latitude,poi_longitude,poi_ratings
good_001,Good Restaurant,restaurant,40.7128,-74.0060,"{4.5,3.8,4.2}"
bad_002,,invalid_category,invalid_lat,invalid_lng,invalid_ratings
good_003,Another Good Restaurant,restaurant,40.7589,-73.9851,"{3.5,4.0}"
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            f.flush()
            
            initial_count = PointOfInterest.objects.count()
            
            # Run import with --stop-on-error
            out = StringIO()
            err = StringIO()
            
            # Should raise exception and stop processing
            with self.assertRaises(SystemExit):
                try:
                    call_command('import_poi', f.name, '--stop-on-error', stdout=out, stderr=err)
                except Exception as e:
                    # Convert any exception to SystemExit for test
                    raise SystemExit(str(e))
            
            # Verify only the first good record was processed
            final_count = PointOfInterest.objects.count()
            # Should have processed first record before hitting error
            self.assertGreaterEqual(final_count - initial_count, 0)
            self.assertLessEqual(final_count - initial_count, 1)
            
        Path(f.name).unlink()
    
    def test_batch_size_option(self):
        """Test that --batch-size option works correctly."""
        csv_content = """poi_id,poi_name,poi_category,poi_latitude,poi_longitude,poi_ratings
batch_001,Batch Restaurant 1,restaurant,40.7128,-74.0060,"{4.5,3.8}"
batch_002,Batch Restaurant 2,restaurant,40.7589,-73.9851,"{3.5,4.0}"
batch_003,Batch Restaurant 3,restaurant,40.7794,-73.9632,"{4.8,4.9}"
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            f.flush()
            
            initial_count = PointOfInterest.objects.count()
            
            # Run import with small batch size
            out = StringIO()
            call_command('import_poi', f.name, '--batch-size', '2', stdout=out)
            
            # Verify all records were imported
            final_count = PointOfInterest.objects.count()
            self.assertEqual(final_count - initial_count, 3)
            
            # Verify output shows completion
            output = out.getvalue()
            self.assertIn('Import completed successfully', output)
            
        Path(f.name).unlink()
    
    def test_verbose_option(self):
        """Test that --verbose option provides detailed logging."""
        csv_content = """poi_id,poi_name,poi_category,poi_latitude,poi_longitude,poi_ratings
verbose_001,Verbose Test Restaurant,restaurant,40.7128,-74.0060,"{4.5,3.8}"
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            f.flush()
            
            # Run import with --verbose
            out = StringIO()
            call_command('import_poi', f.name, '--verbose', stdout=out)
            
            output = out.getvalue()
            
            # Verify verbose output
            self.assertIn('Verbose logging enabled', output)
            self.assertIn('Processing:', output)
            
        Path(f.name).unlink()
    
    def test_glob_pattern_support(self):
        """Test that glob patterns work for file discovery."""
        # Create multiple CSV files
        csv_content = """poi_id,poi_name,poi_category,poi_latitude,poi_longitude,poi_ratings
glob_001,Glob Restaurant,restaurant,40.7128,-74.0060,"{4.5,3.8}"
"""
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create multiple test files
            for i in range(3):
                file_path = temp_path / f"test_data_{i}.csv"
                with open(file_path, 'w') as f:
                    content = csv_content.replace('glob_001', f'glob_{i:03d}')
                    f.write(content)
            
            initial_count = PointOfInterest.objects.count()
            
            # Use glob pattern to import all CSV files
            glob_pattern = str(temp_path / "*.csv")
            out = StringIO()
            call_command('import_poi', glob_pattern, stdout=out)
            
            # Verify all files were processed
            final_count = PointOfInterest.objects.count()
            self.assertEqual(final_count - initial_count, 3)
            
            output = out.getvalue()
            self.assertIn('Found 3 files to process', output)
