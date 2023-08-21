from django.shortcuts import redirect, get_object_or_404
from django.views.generic.list import ListView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.views.generic.base import TemplateResponseMixin, View
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.forms.models import modelform_factory
from django.apps import apps
from django.urls import reverse_lazy
from braces.views import CsrfExemptMixin, JsonRequestResponseMixin

from .models import Course, Module, Content
from .forms import ModuleFormSet


# Mixins
class OwnerMixin:
    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(owner=self.request.user)


class OwnerEditMixin:
    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)


class OwnerCourseMixin(OwnerMixin, LoginRequiredMixin, PermissionRequiredMixin):
    model = Course
    fields = ["subject", "title", "slug", "overview"]
    success_url = reverse_lazy("manage_course_list")


class OwnerCourseEditMixin(OwnerCourseMixin, OwnerEditMixin):
    template_name = "courses/manage/course/form.html"


# Views
class ManageCourseListView(OwnerCourseMixin, ListView):
    template_name = "courses/manage/course/list.html"
    permission_required = "courses.view_course"


class CourseCreateView(OwnerCourseEditMixin, CreateView):
    permission_required = "courses.add_course"


class CourseUpdateView(OwnerCourseEditMixin, UpdateView):
    permission_required = "courses.change_course"


class CourseDeleteView(OwnerCourseMixin, DeleteView):
    template_name = "courses/manage/course/delete.html"
    permission_required = "courses.delete_course"


class CourseModuleUpdateView(TemplateResponseMixin, View):
    template_name = "courses/manage/module/formset.html"
    course = None

    def get_formset(self, data=None):
        return ModuleFormSet(instance=self.course, data=data)

    def dispatch(self, req, pk):
        self.course = get_object_or_404(Course, id=pk, owner=req.user)
        return super().dispatch(req, pk)

    def get(self, req, *args, **kwargs):
        formset = self.get_formset()
        return self.render_to_response({"course": self.course, "formset": formset})

    def post(self, req, *args, **kwargs):
        formset = self.get_formset(data=req.POST)
        if formset.is_valid():
            formset.save()
            return redirect("manage_course_list")

        return self.render_to_response({"formset": formset})


class ContentCreateUpdateView(TemplateResponseMixin, View):
    module = None
    model = None
    obj = None
    template_name = "courses/manage/content/form.html"

    def get_model(self, model_name):
        if model_name in ["text", "file", "image", "video"]:
            return apps.get_model(app_label="courses", model_name=model_name)

        return None

    def get_form(self, model, *args, **kwargs):
        Form = modelform_factory(
            model, exclude=["owner", "order", "created", "updated"]
        )

        return Form(*args, **kwargs)

    def dispatch(self, req, module_id, model_name, id=None):
        self.module = get_object_or_404(Module, id=module_id, course__owner=req.user)
        self.model = self.get_model(model_name)

        if id:
            self.obj = get_object_or_404(self.model, id=id, owner=req.user)

        return super().dispatch(req, module_id, model_name, id)

    def get(self, req, module_id, model_name, id=None):
        form = self.get_form(self.model, instance=self.obj)
        return self.render_to_response({"form": form, "object": self.obj})

    def post(self, req, module_id, model_name, id=None):
        form = self.get_form(
            self.model, instance=self.obj, data=req.POST, files=req.FILES
        )

        if form.is_valid():
            obj = form.save(commit=False)
            obj.owner = req.user
            obj.save()

            if not id:
                # new content
                Content.objects.create(module=self.module, item=obj)

            return redirect("module_content_list", self.module.id)

        return self.render_to_response({"form": form, "object": self.obj})


class ContentDeleteView(View):
    def post(self, req, id):
        content = get_object_or_404(Content, id=id, module__course__owner=req.user)
        module = content.module
        content.item.delete()
        content.delete()

        return redirect("module_content_list", module.id)


class ModuleContentListView(TemplateResponseMixin, View):
    template_name = "courses/manage/module/content_list.html"

    def get(self, req, module_id):
        module = get_object_or_404(Module, id=module_id, course__owner=req.user)
        return self.render_to_response({"module": module})


class ModuleOrderView(CsrfExemptMixin, JsonRequestResponseMixin, View):
    def post(self, req):
        for id, order in self.request_json.items():
            Module.objects.filter(id=id, course__owner=req.user).update(order=order)

        return self.render_json_response({"saved": "OK"})


class ContentOrderView(CsrfExemptMixin, JsonRequestResponseMixin, View):
    def post(self, req):
        for id, order in self.request_json.items():
            Content.objects.filter(id=id, module__course__owner=req.user).update(
                order=order
            )

        return self.render_json_response({"saved": "Ok"})
