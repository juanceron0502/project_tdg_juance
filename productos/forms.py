from struct import calcsize
from productos.models import Producto
from django import forms
from django import forms
from ordenes_de_compra.models import *

from django import forms

from ordenes_de_compra.models import Orden
from productos.models import Producto, RevisionCalificacion


class ProductoForm(forms.ModelForm):

    class Meta:
        model = Producto
        fields = [
            'nombre', 'precio', 'unidad_precio', 'producto_sipsa',
            'stock', 'Informacion_de_produccion', 'descripcion',
            'image', 'categoria',
        ]
        labels = {
            'precio': 'Precio',
            'unidad_precio': 'El precio es por',
            'producto_sipsa': 'Referencia de precio de mercado',
        }
        help_texts = {
            'producto_sipsa': (
                'Si su producto es papa, tomate o habichuela, selecciónelo para ver '
                'el precio de referencia del mercado mayorista de Popayán.'
            ),
            'unidad_precio': (
                'La comparación con el mercado solo se muestra cuando el precio es por kilogramo.'
            ),
        }

    def clean_precio(self):
        precio = self.cleaned_data['precio']
        if precio <= 0:
            raise forms.ValidationError('El precio debe ser mayor que cero.')
        return precio

    def clean_stock(self):
        stock = self.cleaned_data['stock']
        if stock < 0:
            raise forms.ValidationError('El stock no puede ser negativo.')
        return stock


class OrdenForm(forms.ModelForm):
    class Meta:
        model = Orden
        fields = [
            'nombres', 'apellidos', 'numero_telefono', 'email',
            'direccion_linea_1', 'direccion_linea_2', 'ciudad',
            'departamento', 'orden_descripcion',
        ]


class comentarioform(forms.ModelForm):
    class Meta:
        model = RevisionCalificacion
        fields = ['Sujeto', 'comentario', 'calificacion']

    def clean_calificacion(self):
        calificacion = self.cleaned_data['calificacion']
        if not 1 <= calificacion <= 5:
            raise forms.ValidationError('La calificación debe estar entre 1 y 5.')
        return calificacion