import factory
from django.contrib.auth.models import User

from library.models import Article


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    password = factory.PostGenerationMethodCall("set_password", "pw12345")


class ArticleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Article

    owner = factory.SubFactory(UserFactory)
    url = factory.Faker("url")
