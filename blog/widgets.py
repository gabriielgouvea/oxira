from django import forms

class ImageCropWidget(forms.ClearableFileInput):
    template_name = 'widgets/image_crop_widget.html'

    def __init__(self, attrs=None):
        super().__init__(attrs)

    class Media:
        css = {
            'all': (
                'https://cdnjs.cloudflare.com/ajax/libs/cropperjs/1.5.13/cropper.min.css',
            )
        }
        js = (
            'https://cdnjs.cloudflare.com/ajax/libs/cropperjs/1.5.13/cropper.min.js',
        )
