import factory
from django.utils import timezone

from updates.models import Update


class UpdateFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Update

    title = factory.Faker("sentence", nb_words=4)
    content = factory.Faker("paragraph", nb_sentences=5)
    is_published = True
    published_at = factory.LazyFunction(timezone.now)


class UnpublishedUpdateFactory(UpdateFactory):
    is_published = False
    published_at = None
