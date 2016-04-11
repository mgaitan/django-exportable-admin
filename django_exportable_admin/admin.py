from collections import OrderedDict

from django.conf.urls import patterns, url
from django.contrib import admin
from django.contrib.admin.utils import lookup_field, label_for_field
from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse
from django.http import StreamingHttpResponse
from django.utils import six
from django.utils.encoding import iri_to_uri
from django.utils.html import strip_tags
from django.utils.text import slugify

from .utils import UnicodeWriter, Echo


import logging

log = logging.getLogger(__name__)


class ExportableAdmin(admin.ModelAdmin):
    """
    Base class which contains all of the functionality to setup admin
    changelist export. Subclassing this class itself will do nothing unless you
    set export_formats on your ModelAdmin instance. See the other provided
    subclasses which are already setup for CSV, Pipe, and both.

    Note: do not override change_list_template or you will not get the
    "Export ..." button on your changelist page.
    """
    # use a custom changelist template which adds "Export ..." button(s)
    change_list_template = 'django_exportable_admin/change_list_exportable.html'

    # an iterable of 2-tuples of (format-name, format-delimiter), such as:
    #  ((u'CSV', u','), (u'Pipe', u'|'),)
    export_formats = (
        (u'CSV', u','),
        (u'Tab Delimited', u'\t'),
    )

    def get_export_buttons(self, request):
        """
        Returns a iterable of 2-tuples which contain:
            (button text, link URL)

        These will be used in the customized changelist template to output a
        button for each export format.
        """
        app = self.model._meta.app_label
        try:
            mod = self.model._meta.module_name
        except AttributeError:
            mod = self.model._meta.model_name

        return (
            (
                'Export as %s' % format_name,
                '%s%s' % (
                    reverse("admin:%s_%s_export_%s" % (
                        app, mod, format_name.lower())),
                    ('?' + iri_to_uri(request.META.get('QUERY_STRING', '')))
                    if request.META.get('QUERY_STRING', '') else '')
             ) for format_name, delimiter in self.export_formats
        )

    def export_changelist_view(self, request, extra_context=None):
        delimiter = (extra_context or {}).get('export_delimiter', None)

        response = super(ExportableAdmin, self).changelist_view(
            request, extra_context)
        cl = response.context_data['cl']

        # get headers
        res_headers = OrderedDict()
        for field_name in cl.list_display:
            if field_name == 'action_checkbox':
                continue

            label = label_for_field(
                field_name, cl.model,
                model_admin=cl.model_admin)
            res_headers[field_name] = label

        pseudo_buffer = Echo()

        # get result rows
        def generate_response():
            csv = UnicodeWriter(
                pseudo_buffer,
                fieldnames=res_headers.values(),
                delimiter=str(delimiter))

            for result in cl.queryset.iterator():
                row = {}
                for field_name in cl.list_display:
                    if field_name == 'action_checkbox':
                        continue
                    try:
                        _, _, value = lookup_field(
                            field_name, result, cl.model_admin)
                    except ObjectDoesNotExist:
                        value = None

                    if isinstance(value, six.string_types):
                        value = strip_tags(value)
                    row[res_headers[field_name]] = value

                yield csv.writerow(row)

        # build response csv
        response = StreamingHttpResponse(
            generate_response(), content_type='text/csv')
        response['Content-Disposition'] = \
            'attachment; filename={0}.csv'.format(
                slugify(self.model._meta.verbose_name))
        return response

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context.update({
            'export_buttons': self.get_export_buttons(request),
        })
        return super(ExportableAdmin, self).changelist_view(
            request, extra_context)

    def get_urls(self):
        """
        Add URL patterns for the export formats. Really all these URLs do are
        set extra_context to contain the export_delimiter for the template
        which actually generates the "CSV".
        """
        urls = super(ExportableAdmin, self).get_urls()
        app = self.model._meta.app_label
        try:
            mod = self.model._meta.model_name
        except AttributeError:
            mod = self.model._meta.model_name
        # make a URL pattern for each export format
        new_urls = [
            url(
                r'^export/%s$' % format_name.lower(),
                self.admin_site.admin_view(self.export_changelist_view),
                name="%s_%s_export_%s" % (app, mod, format_name.lower()),
                kwargs={'extra_context': {'export_delimiter': delimiter}},
            )
            for format_name, delimiter in self.export_formats
        ]
        my_urls = patterns('', *new_urls)
        return my_urls + urls


class CSVExportableAdmin(ExportableAdmin):
    """
    ExportableAdmin subclass which adds export to CSV functionality.

    Note: do not override change_list_template or you will not get the
    "Export ..." button on your changelist page.
    """
    export_formats = (
        (u'CSV', u','),
    )


class PipeExportableAdmin(ExportableAdmin):
    """
    ExportableAdmin subclass which adds export to Pipe functionality.

    Note: do not override change_list_template or you will not get the
    "Export ..." button on your changelist page.
    """
    export_formats = (
        (u'Pipe', u'|'),
    )


class MultiExportableAdmin(ExportableAdmin):
    """
    ExportableAdmin subclass which adds export to CSV and Pipe
    functionality.

    Note: do not override change_list_template or you will not get the
    "Export ..." buttons on your changelist page.
    """
    export_formats = (
        (u'CSV', u','),
        (u'Pipe', u'|'),
    )
