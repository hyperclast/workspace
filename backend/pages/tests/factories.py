import factory
from datetime import timedelta
from django.utils import timezone

from pages.models import (
    Page,
    PageEditorAddEvent,
    PageEditorRemoveEvent,
    PageInvitation,
    Project,
    ProjectEditor,
    ProjectEditorAddEvent,
    ProjectEditorRemoveEvent,
    ProjectInvitation,
)
from users.tests.factories import OrgFactory, UserFactory


class ProjectFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Project

    org = factory.SubFactory(OrgFactory)
    name = factory.Faker("catch_phrase")
    description = factory.Faker("text", max_nb_chars=200)
    is_deleted = False
    creator = factory.SubFactory(UserFactory)


class PageFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Page

    project = factory.SubFactory("pages.tests.factories.ProjectFactory")
    creator = factory.SubFactory(UserFactory)
    title = factory.Faker("sentence", nb_words=2)
    details = factory.Dict({"content": ""})

    @factory.post_generation
    def add_owner_as_editor(obj, create, extracted, **kwargs):
        """Automatically add the owner as an editor after creation."""
        if create:
            obj.editors.add(obj.creator)


class PageInvitationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PageInvitation

    page = factory.SubFactory(PageFactory)
    email = factory.Faker("email")
    invited_by = factory.SubFactory(UserFactory)
    token = factory.Faker("sha256")
    accepted = False
    expires_at = factory.LazyFunction(lambda: timezone.now() + timedelta(days=7))


class PageEditorAddEventFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PageEditorAddEvent

    page = factory.SubFactory(PageFactory)
    added_by = factory.SubFactory(UserFactory)
    editor = factory.SubFactory(UserFactory)
    editor_email = factory.LazyAttribute(
        lambda obj: obj.editor.email if obj.editor else factory.Faker("email").generate()
    )


class PageEditorRemoveEventFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PageEditorRemoveEvent

    page = factory.SubFactory(PageFactory)
    removed_by = factory.SubFactory(UserFactory)
    editor = factory.SubFactory(UserFactory)
    editor_email = factory.LazyAttribute(
        lambda obj: obj.editor.email if obj.editor else factory.Faker("email").generate()
    )


class ProjectEditorFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProjectEditor

    user = factory.SubFactory(UserFactory)
    project = factory.SubFactory(ProjectFactory)


class ProjectEditorAddEventFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProjectEditorAddEvent

    project = factory.SubFactory(ProjectFactory)
    added_by = factory.SubFactory(UserFactory)
    editor = factory.SubFactory(UserFactory)
    editor_email = factory.LazyAttribute(
        lambda obj: obj.editor.email if obj.editor else factory.Faker("email").generate()
    )


class ProjectEditorRemoveEventFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProjectEditorRemoveEvent

    project = factory.SubFactory(ProjectFactory)
    removed_by = factory.SubFactory(UserFactory)
    editor = factory.SubFactory(UserFactory)
    editor_email = factory.LazyAttribute(
        lambda obj: obj.editor.email if obj.editor else factory.Faker("email").generate()
    )


class ProjectInvitationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProjectInvitation

    project = factory.SubFactory(ProjectFactory)
    email = factory.Faker("email")
    invited_by = factory.SubFactory(UserFactory)
    token = factory.Faker("sha256")
    accepted = False
    expires_at = factory.LazyFunction(lambda: timezone.now() + timedelta(days=7))
