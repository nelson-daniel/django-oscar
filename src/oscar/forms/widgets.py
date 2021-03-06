import copy
import re

from django import forms
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.forms.utils import flatatt
from django.forms.widgets import FileInput
from django.utils import formats, six
from django.utils.encoding import force_text
from django.utils.safestring import mark_safe
from django.utils.six.moves import filter, map


class ImageInput(FileInput):
    """
    Widget providing a input element for file uploads based on the
    Django ``FileInput`` element. It hides the actual browser-specific
    input element and shows the available image for images that have
    been previously uploaded. Selecting the image will open the file
    dialog and allow for selecting a new or replacing image file.
    """
    template_name = 'oscar/forms/widgets/image_input_widget.html'

    def __init__(self, attrs=None):
        if not attrs:
            attrs = {}
        attrs['accept'] = 'image/*'
        super(ImageInput, self).__init__(attrs=attrs)

    def get_context(self, name, value, attrs):
        ctx = super(ImageInput, self).get_context(name, value, attrs)

        ctx['image_url'] = ''
        if value and not isinstance(value, InMemoryUploadedFile):
            # can't display images that aren't stored - pass empty string to context
            ctx['image_url'] = value

        ctx['image_id'] = "%s-image" % ctx['widget']['attrs']['id']
        return ctx


class WYSIWYGTextArea(forms.Textarea):

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('attrs', {})
        kwargs['attrs'].setdefault('class', '')
        kwargs['attrs']['class'] += ' wysiwyg'
        super(WYSIWYGTextArea, self).__init__(*args, **kwargs)


def datetime_format_to_js_date_format(format):
    """
    Convert a Python datetime format to a date format suitable for use with
    the JS date picker we use.
    """
    format = format.split()[0]
    return datetime_format_to_js_datetime_format(format)


def datetime_format_to_js_time_format(format):
    """
    Convert a Python datetime format to a time format suitable for use with the
    JS time picker we use.
    """
    try:
        format = format.split()[1]
    except IndexError:
        pass
    converted = format
    replacements = {
        '%H': 'hh',
        '%I': 'HH',
        '%M': 'ii',
        '%S': 'ss',
    }
    for search, replace in replacements.items():
        converted = converted.replace(search, replace)
    return converted.strip()


def datetime_format_to_js_datetime_format(format):
    """
    Convert a Python datetime format to a time format suitable for use with
    the datetime picker we use, http://www.malot.fr/bootstrap-datetimepicker/.
    """
    converted = format
    replacements = {
        '%Y': 'yyyy',
        '%y': 'yy',
        '%m': 'mm',
        '%d': 'dd',
        '%H': 'hh',
        '%I': 'HH',
        '%M': 'ii',
        '%S': 'ss',
    }
    for search, replace in replacements.items():
        converted = converted.replace(search, replace)

    return converted.strip()


def datetime_format_to_js_input_mask(format):
    # taken from
    # http://stackoverflow.com/questions/15175142/how-can-i-do-multiple-substitutions-using-regex-in-python  # noqa
    def multiple_replace(dict, text):
        # Create a regular expression  from the dictionary keys
        regex = re.compile("(%s)" % "|".join(map(re.escape, dict.keys())))

        # For each match, look-up corresponding value in dictionary
        return regex.sub(lambda mo: dict[mo.string[mo.start():mo.end()]], text)

    replacements = {
        '%Y': 'y',
        '%y': '99',
        '%m': 'm',
        '%d': 'd',
        '%H': 'h',
        '%I': 'h',
        '%M': 's',
        '%S': 's',
    }
    return multiple_replace(replacements, format).strip()


class DateTimeWidgetMixin(object):

    template_name = 'oscar/forms/widgets/date_time_picker.html'

    def get_format(self):
        return self.format or formats.get_format(self.format_key)[0]

    def build_attrs(self, base_attrs, extra_attrs=None):
        attrs = super(DateTimeWidgetMixin, self).build_attrs(base_attrs, extra_attrs)
        attrs['data-inputmask'] = u"'mask': '{mask}'".format(
            mask=datetime_format_to_js_input_mask(self.get_format()))
        return attrs


class TimePickerInput(DateTimeWidgetMixin, forms.TimeInput):
    """
    A widget that passes the date format to the JS date picker in a data
    attribute.
    """
    format_key = 'TIME_INPUT_FORMATS'

    def get_context(self, name, value, attrs):
        ctx = super(TimePickerInput, self).get_context(name, value, attrs)
        ctx['div_attrs'] = {
            'data-oscarWidget': 'time',
            'data-timeFormat': datetime_format_to_js_time_format(self.get_format()),
        }
        ctx['icon_classes'] = 'icon-time glyphicon-time'
        return ctx


class DatePickerInput(DateTimeWidgetMixin, forms.DateInput):
    """
    A widget that passes the date format to the JS date picker in a data
    attribute.
    """
    format_key = 'DATE_INPUT_FORMATS'

    def get_context(self, name, value, attrs):
        ctx = super(DatePickerInput, self).get_context(name, value, attrs)
        ctx['div_attrs'] = {
            'data-oscarWidget': 'date',
            'data-dateFormat': datetime_format_to_js_date_format(self.get_format()),
        }
        ctx['icon_classes'] = 'icon-calendar glyphicon-calendar'
        return ctx


class DateTimePickerInput(DateTimeWidgetMixin, forms.DateTimeInput):
    """
    A widget that passes the datetime format to the JS datetime picker in a
    data attribute.

    It also removes seconds by default. However this only works with widgets
    without localize=True.

    For localized widgets refer to
    https://docs.djangoproject.com/en/1.11/topics/i18n/formatting/#creating-custom-format-files # noqa
    instead to override the format.
    """
    format_key = 'DATETIME_INPUT_FORMATS'

    def __init__(self, *args, **kwargs):
        include_seconds = kwargs.pop('include_seconds', False)
        super(DateTimePickerInput, self).__init__(*args, **kwargs)

        if not include_seconds and self.format:
            self.format = re.sub(':?%S', '', self.format)

    def get_context(self, name, value, attrs):
        ctx = super(DateTimePickerInput, self).get_context(name, value, attrs)
        ctx['div_attrs'] = {
            'data-oscarWidget': 'datetime',
            'data-datetimeFormat': datetime_format_to_js_datetime_format(self.get_format()),
        }
        ctx['icon_classes'] = 'icon-calendar glyphicon-calendar'
        return ctx


class AdvancedSelect(forms.Select):
    """
    Customised Select widget that allows a list of disabled values to be passed
    to the constructor.  Django's default Select widget doesn't allow this so
    we have to override the render_option method and add a section that checks
    for whether the widget is disabled.
    """

    def __init__(self, attrs=None, choices=(), disabled_values=()):
        self.disabled_values = set(force_text(v) for v in disabled_values)
        super(AdvancedSelect, self).__init__(attrs, choices)

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super(AdvancedSelect, self).create_option(name, value, label, selected, index, subindex, attrs)
        if force_text(value) in self.disabled_values:
            option['attrs']['disabled'] = True
        return option


class RemoteSelect(forms.Widget):
    """
    Somewhat reusable widget that allows AJAX lookups in combination with
    select2.
    Requires setting the URL of a lookup view either as class attribute or when
    constructing
    """
    is_multiple = False
    lookup_url = None
    template_name = None

    def __init__(self, *args, **kwargs):
        if 'lookup_url' in kwargs:
            self.lookup_url = kwargs.pop('lookup_url')
        if self.lookup_url is None:
            raise ValueError(
                "RemoteSelect requires a lookup ULR")
        super(RemoteSelect, self).__init__(*args, **kwargs)

    def format_value(self, value):
        return six.text_type(value or '')

    def value_from_datadict(self, data, files, name):
        value = data.get(name, None)
        if value is None:
            return value
        else:
            return six.text_type(value)

    def render(self, name, value, attrs=None, renderer=None):
        attrs = {} if attrs is None else copy.copy(attrs)
        attrs.update({
            'type': 'hidden',
            'name': name,
            'data-ajax-url': self.lookup_url,
            'data-multiple': 'multiple' if self.is_multiple else '',
            'value': self.format_value(value),
            'data-required': 'required' if self.is_required else '',
        })
        return mark_safe(u'<input %s>' % flatatt(attrs))


class MultipleRemoteSelect(RemoteSelect):
    is_multiple = True

    def format_value(self, value):
        if value:
            return ','.join(map(six.text_type, filter(bool, value)))
        else:
            return ''

    def value_from_datadict(self, data, files, name):
        value = data.get(name, None)
        if value is None:
            return []
        else:
            return list(filter(bool, value.split(',')))
