import factory
from django.contrib.auth import get_user_model
from faker import Faker

from users.constants import OrgMemberRole
from users.models import Org, OrgMember


User = get_user_model()


TEST_USER_PASSWORD = "testpass1234"


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        exclude = "text_password"

    username = factory.Faker("user_name")
    email = factory.Faker("email")
    password = factory.PostGenerationMethodCall("set_password", TEST_USER_PASSWORD)

    @classmethod
    def create(cls, **kwargs):
        profile_details = {}
        keys_to_pop = []

        for k, v in kwargs.items():
            if not k.startswith("profile__"):
                continue

            profile_field = k.split("__")[-1]
            profile_details[profile_field] = v
            keys_to_pop.append(k)

        for p in keys_to_pop:
            kwargs.pop(p)

        user = super().create(**kwargs)

        if profile_details:
            for fld, val in profile_details.items():
                setattr(user.profile, fld, val)

            user.profile.save()

        return user


class OrgFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Org

    name = factory.Faker("company")
    domain = factory.Sequence(lambda n: f"company{n}.com")


class OrgMemberFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = OrgMember

    org = factory.SubFactory(OrgFactory)
    user = factory.SubFactory(UserFactory)
    role = OrgMemberRole.MEMBER.value
