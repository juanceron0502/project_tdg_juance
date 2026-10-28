from multiprocessing import context
from django.shortcuts import render, get_object_or_404, redirect
from .models import *
from cuentas.models import *
from categorias.models import *
from carrito.models import *
from carrito.views import _carrito_id
from django.contrib import messages
from django.db.models import Q
from .forms import *
from django.contrib.auth.decorators import  login_required
from cuentas.models import *
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from ordenes_de_compra.models import OrdenProducto
from django.views.decorators.http import require_POST
from django.http import JsonResponse

# Create your views here.

def verproducto (request, categoria_slug=None):
    categorias =None
    productos =None

    if categoria_slug !=None:
        categorias = get_object_or_404(Categoria, slug=categoria_slug)
        productos = Producto.objects.filter(categoria=categorias, activo=True)
        paginator = Paginator(productos, 5)
        page = request.GET.get('page')
        page_productos = paginator.get_page(page)
        product_count = productos.count()

    else:
        productos = Producto.objects.all().filter(activo=True)
        paginator = Paginator(productos, 5)
        page = request.GET.get('page')
        page_productos = paginator.get_page(page)
        product_count = productos.count()

    context = {
        'productos' :page_productos, 
        'product_count':product_count,
        
    }

    return render (request, 'categorias/vercategoria.html',context)


def detalleproducto(request, categoria_slug, producto_slug):
    single_producto = get_object_or_404(
        Producto, categoria__slug=categoria_slug, slug=producto_slug)

    le_gusta = (request.user.is_authenticated
                and single_producto.likes.filter(user=request.user).exists())

    comentarios = RevisionCalificacion.objects.filter(
        producto=single_producto, estado=True)

    es_dueno = request.user.is_authenticated and (
        request.user.pk == single_producto.user_id or request.user.is_staff)
    comparacion = single_producto.comparacion_referencia() if es_dueno else None

    context = {
        'single_producto': single_producto,
        'le_gusta': le_gusta,
        'comentarios': comentarios,
        'comparacion': comparacion,
    }
    return render(request, 'verproducts/verproductos.html', context)

def buscador(request):
    keyword = request.GET.get('keyword', '').strip()
    productos = Producto.objects.none()
    users = Cuentas.objects.none()

    if keyword:
        users = Cuentas.objects.filter(Q(nombres__icontains=keyword))
        productos = (Producto.objects.filter(activo=True)
                     .filter(Q(descripcion__icontains=keyword) | Q(nombre__icontains=keyword))
                     .order_by('-fecha_creacion'))

    context = {
        'productos': productos,
        'producto_count': productos.count(),
        'users': users,
    }
    return render(request, 'categorias/vercategoria.html', context)

@login_required
def agregar_Producto(request):
    current_user = get_object_or_404(Cuentas, pk=request.user.pk)

    if request.method == 'POST':
        formulario = ProductoForm(data=request.POST, files=request.FILES)
        if formulario.is_valid():
            producto = formulario.save(commit=False)
            producto.user = current_user
            producto.save()
            messages.success(request, 'producto cargado')
            return redirect ('inicio')

    else:
        formulario = ProductoForm()

    return render(request, 'producto/agregarproducto.html', {'formulario' : formulario})
@login_required
def listar_productos(request):
    productos = Producto.objects.all()
    data ={
        'productos': productos
    }
    return render(request, 'producto/listar.html', data)

@login_required
def modificar_producto(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    if producto.user_id != request.user.pk and not request.user.is_superuser:
        messages.error(request, 'No tienes permiso para modificar este producto')
        return redirect('inicio')

    data = {'form': ProductoForm(instance=producto)}
    if request.method == 'POST':
        form = ProductoForm(data=request.POST, instance=producto, files=request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Producto Modificado con Exito')
            return redirect("tablero")
        data["form"] = form
    return render(request, 'producto/modificar.html', data)


@login_required
def eliminar_producto(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    if producto.user_id != request.user.pk and not request.user.is_superuser:
        messages.error(request, 'No tienes permiso para eliminar este producto')
        return redirect('inicio')
    producto.delete()
    messages.success(request, 'Producto Eliminado con Exito')
    return redirect(to="tablero")


def verificar(request):
    return render(request, 'producto/verificar.html')




"""def productos (request):
    product = Producto.objects.all().filter(activo = True)

    context = {
        'product': product,
    }
    return render (request, 'productos.html', context)"""



def productos_usuario (request):
    product = Producto.objects.all().filter(activo = True)

    context = {
        'product': product,
    }
    return render (request, 'productos.html', context)
 

def verproducto_usuario (request, pk):
    verproducto = Producto.objects.filter(pk=pk)

    context={
        'verproducto':verproducto,
    }
    return render(request, 'verproducts/verproductos_usuario.html', context) 

def comentarios_calf (request, producto_id):
    url = request.META.get('HTTP_REFERER')
    if request.method == 'POST':
        try:
            comentarios = RevisionCalificacion.objects.get(user__id=request.user.id, producto__id=producto_id)
            form = comentarioform(request.POST, instance=comentarios)
            form.save()
            messages.success(request, 'Muchas Gracias! Tu comentario ha sido cargado')
            return redirect(url)
        except RevisionCalificacion .DoesNotExist:
            form = comentarioform(request.POST)
            if form.is_valid():
                data = RevisionCalificacion()
                data.Sujeto = form.cleaned_data['Sujeto']    
                data.calificacion= form.cleaned_data['calificacion']    
                data.comentario = form.cleaned_data['comentario']    
                data.ip = request.META.get('REMOTE_ADDR')   
                data.producto_id = producto_id     
                data.user_id = request.user.id     
                data.save()
                messages.success(request, 'Muchas Gracias! Tu comentario fue enviado con exito')
                return redirect(url) 


@login_required
@require_POST

def toggle_like(request, pk):
    producto = get_object_or_404(Producto, pk=pk)

    like, creado = Like.objects.get_or_create(user=request.user, producto=producto)
    if not creado:
        like.delete()          # si ya existía, se quita (funciona como interruptor)

    # Petición con JavaScript (fetch): responde JSON, sin recargar la página
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "liked": creado,
            "total": producto.likes.count(),
        })

    # Sin JavaScript: vuelve a la página del producto
    return redirect(producto.get_url())




