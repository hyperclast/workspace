import factory
from datetime import timedelta
from django.utils import timezone

from pages.constants import PageEditorRole
from pages.models import (
    Comment,
    CommentReaction,
    Folder,
    Page,
    PageEditor,
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


class FolderFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Folder

    project = factory.SubFactory("pages.tests.factories.ProjectFactory")
    name = factory.Faker("word")
    parent = None


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
    role = PageEditorRole.VIEWER.value


class PageEditorFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PageEditor

    user = factory.SubFactory(UserFactory)
    page = factory.SubFactory(PageFactory)
    role = PageEditorRole.VIEWER.value


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


class CommentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Comment

    page = factory.SubFactory(PageFactory)
    author = factory.SubFactory(UserFactory)
    body = factory.Faker("sentence")
    parent = None
    ai_persona = ""
    requester = None

    @factory.lazy_attribute
    def root(self):
        if self.parent:
            return self.parent.root if self.parent.root_id else self.parent
        return None

    @factory.lazy_attribute
    def depth(self):
        if self.parent:
            return self.parent.depth + 1
        return 0

    @factory.lazy_attribute
    def anchor_text(self):
        # Replies must not have anchor_text (DB constraint: replies_no_anchor)
        if self.parent:
            return ""
        return factory.Faker("sentence").evaluate(None, None, {"locale": None})


class CommentReactionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CommentReaction

    comment = factory.SubFactory(CommentFactory)
    user = factory.SubFactory(UserFactory)
    emoji = "👍"
