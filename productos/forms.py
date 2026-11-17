from struct import calcsize
from productos.models import Producto
from django import forms
from django import forms


from django import forms

from productos.models import Producto, RevisionCalificacion
from inteligencia_artificial.services.recomendaciones import cargar_recomendaciones

class ProductoForm(forms.ModelForm):
    producto_sipsa = forms.ChoiceField(
        required=False,
        label='Referencia de precio de mercado',
        help_text=('Si su producto tiene referencia en el mercado mayorista de Popayán, '
                   'selecciónelo para comparar su precio.'),
    )

    class Meta:
        model = Producto
        fields = [
            'nombre', 'precio', 'unidad_precio', 'producto_sipsa',
            'stock', 'Informacion_de_produccion', 'descripcion',
            'image', 'categoria',
        ]
        labels = {
            'unidad_precio': 'El precio es por',
            'descripcion': 'Descripción',
            'image': 'Imagen',
            'Informacion_de_produccion': 'Información de producción',
        }
        
        help_texts = {
            'unidad_precio': 'La comparación con el mercado solo se muestra si el precio es por kilogramo.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        opciones = [("", "Sin referencia de precio")]
        opciones += sorted(
            (r["producto"], f"{r['producto']} (confianza {r['confianza'].lower()})")
            for r in cargar_recomendaciones()
        )
        # Si el producto ya tenía un valor que dejó de existir, no se pierde al editar
        actual = self.instance.producto_sipsa if self.instance and self.instance.pk else ""
        if actual and actual not in dict(opciones):
            opciones.append((actual, f"{actual} (sin referencia vigente)"))
        self.fields["producto_sipsa"].choices = opciones

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





class comentarioform(forms.ModelForm):
    class Meta:
        model = RevisionCalificacion
        fields = ['Sujeto', 'comentario', 'calificacion']

    def clean_calificacion(self):
        calificacion = self.cleaned_data['calificacion']
        if not 1 <= calificacion <= 5:
            raise forms.ValidationError('La calificación debe estar entre 1 y 5.')
        return calificacion