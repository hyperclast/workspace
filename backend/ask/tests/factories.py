import factory
from django.utils import timezone

from ask.models import AskRequest, PageEmbedding


class PageEmbeddingFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PageEmbedding

    page = factory.SubFactory("pages.tests.factories.PageFactory")
    embedding = factory.LazyFunction(lambda: [0.0] * 1536)
    computed = factory.LazyFunction(timezone.now)


class AskRequestFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AskRequest

    user = factory.SubFactory("users.tests.factories.UserFactory")
    query = factory.Faker("sentence", nb_words=3)
