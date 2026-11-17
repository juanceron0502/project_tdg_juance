from django.conf import settings
from django.db import models
from django.db.models import Avg
from django.urls import reverse
from django.utils import timezone
from autoslug import AutoSlugField

from categorias.models import Categoria
from cuentas.models import Cuentas

UNIDADES_PRECIO = [
    ("kg", "Kilogramo"),
    ("lb", "Libra"),
    ("bulto", "Bulto"),
    ("unidad", "Unidad"),
]


class Producto(models.Model):
    user = models.ForeignKey(Cuentas, on_delete=models.CASCADE, related_name='product')
    nombre = models.CharField(max_length=50)
    slug = AutoSlugField(populate_from='nombre')
    precio = models.FloatField()
    unidad_precio = models.CharField(max_length=10, choices=UNIDADES_PRECIO, default="kg")
    # Nombre exacto del producto en el SIPSA. Las opciones las arma el formulario
    # a partir de recomendaciones.json, por eso aquí no lleva "choices".
    producto_sipsa = models.CharField(
        max_length=100, blank=True,
        help_text="Producto equivalente en el SIPSA, si tiene precio de referencia",
    )
    Informacion_de_produccion = models.CharField(max_length=100)
    image = models.ImageField()
    stock = models.IntegerField()
    timestamp = models.DateTimeField(default=timezone.now)
    descripcion = models.TextField()
    categoria = models.ForeignKey(Categoria, on_delete=models.CASCADE, related_name='productoscat')
    destacado = models.BooleanField(default=True)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    modificacion_date = models.DateTimeField(auto_now=True)

    def referencia_precio(self):
        # Import local para evitar importaciones circulares
        from inteligencia_artificial.services.recomendaciones import recomendacion_de
        return recomendacion_de(self.producto_sipsa)

    def comparacion_referencia(self):
        """Compara el precio del productor con la referencia, solo si ambos son por kg."""
        r = self.referencia_precio()
        if not r or self.unidad_precio != "kg" or not r["precio_estimado"]:
            return None
        return {
            "referencia": r,
            "diferencia_pct": round((self.precio / r["precio_estimado"] - 1) * 100),
            "dentro_rango": r["rango_bajo"] <= self.precio <= r["rango_alto"],
        }

    def get_url(self):
        return reverse('detalleproducto', args=[self.categoria.slug, self.slug])

    def __str__(self):
        return self.nombre

    def revisionPromedio(self):
        r = RevisionCalificacion.objects.filter(
            producto=self, estado=True).aggregate(revision=Avg('calificacion'))
        return float(r['revision']) if r['revision'] is not None else 0

    class Meta:
        verbose_name = 'Producto'
        verbose_name_plural = 'Productos'
        ordering = ['-id']


class KardexManager(models.Manager):
    def calidades(self):
        return super().filter(kardex_categoria='calidad', activo=True)

    def cantidades(self):
        return super().filter(kardex_categoria='cantidad', activo=True)


kardex_categoria_choice = (
    ('calidad', 'calidad'),
    ('cantidad', 'cantidad'),
)


class Kardex(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    kardex_categoria = models.CharField(max_length=100, choices=kardex_categoria_choice)
    kardex_value = models.CharField(max_length=100)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now=True)

    objects = KardexManager()

    def __str__(self):
        return self.kardex_categoria + ':' + self.kardex_value


class RevisionCalificacion(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    user = models.ForeignKey(Cuentas, on_delete=models.CASCADE)
    Sujeto = models.CharField(max_length=200, blank=True)
    comentario = models.CharField(max_length=500, blank=True)
    calificacion = models.FloatField()
    ip = models.CharField(max_length=45)
    estado = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_subido = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.Sujeto


class Like(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="likes",
    )
    producto = models.ForeignKey(
        Producto,
        on_delete=models.CASCADE,
        related_name="likes",
    )
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Un usuario solo puede dar un me gusta por producto
        constraints = [
            models.UniqueConstraint(fields=["user", "producto"], name="unique_like_user_producto"),
        ]

    def __str__(self):
        return f"{self.user} ♥ {self.producto}"