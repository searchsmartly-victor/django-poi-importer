"""
Factory classes for creating test data.
"""

from decimal import Decimal
from typing import List

import factory
from factory.django import DjangoModelFactory

from ingest.models import PointOfInterest


class PointOfInterestFactory(DjangoModelFactory):
    """
    Factory for creating PointOfInterest test instances.
    """
    
    class Meta:
        model = PointOfInterest
    
    external_id = factory.Sequence(lambda n: f"test_poi_{n}")
    source = factory.Iterator(['csv', 'json', 'xml'])
    name = factory.Faker('company')
    latitude = factory.Faker(
        'pydecimal', 
        left_digits=2, 
        right_digits=6, 
        positive=False,
        min_value=Decimal('-90'),
        max_value=Decimal('90')
    )
    longitude = factory.Faker(
        'pydecimal',
        left_digits=3,
        right_digits=6, 
        positive=False,
        min_value=Decimal('-180'),
        max_value=Decimal('180')
    )
    category = factory.Iterator([
        'restaurant', 'hotel', 'museum', 'park', 'school', 
        'hospital', 'pharmacy', 'bus-stop', 'coffee-shop'
    ])
    ratings_raw = factory.LazyAttribute(
        lambda obj: [3.0, 4.0, 3.5, 4.2, 3.8]  # Default ratings
    )
    avg_rating = factory.LazyAttribute(
        lambda obj: Decimal('3.70')  # Average of default ratings
    )
    description = factory.Faker('text', max_nb_chars=200)
    
    @factory.post_generation
    def custom_ratings(self, create: bool, extracted: List[float], **kwargs) -> None:
        """
        Post-generation hook to set custom ratings and recalculate average.
        
        Usage:
            PointOfInterestFactory(custom_ratings=[4.0, 5.0, 3.0])
        """
        if not create:
            return
        
        if extracted is not None:
            self.ratings_raw = extracted
            if extracted:
                avg = sum(extracted) / len(extracted)
                self.avg_rating = Decimal(str(round(avg, 2)))
            else:
                self.avg_rating = Decimal('0.00')
            self.save(update_fields=['ratings_raw', 'avg_rating'])


class PointOfInterestFactoryCSV(PointOfInterestFactory):
    """
    Factory specifically for CSV-sourced POIs.
    """
    source = 'csv'
    external_id = factory.Sequence(lambda n: f"csv_{n}")


class PointOfInterestFactoryJSON(PointOfInterestFactory):
    """
    Factory specifically for JSON-sourced POIs.
    """
    source = 'json'
    external_id = factory.Sequence(lambda n: f"json_{n}")


class PointOfInterestFactoryXML(PointOfInterestFactory):
    """
    Factory specifically for XML-sourced POIs.
    """
    source = 'xml'
    external_id = factory.Sequence(lambda n: f"xml_{n}")
