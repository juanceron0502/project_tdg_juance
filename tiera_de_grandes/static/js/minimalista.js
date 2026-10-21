/* ==========================================================================
   Tierra de Grandes - Interacciones y Accesibilidad
   ========================================================================== */

document.addEventListener('DOMContentLoaded', () => {

    // 1. FORMATO DE MONEDA AUTOMÁTICO
    // Asegura que precios como "50000,0" (visto en tu video) se formateen a "$50.000" para fácil lectura
    const precios = document.querySelectorAll('.precio-producto');
    precios.forEach(precioEl => {
        let textoPrecio = precioEl.innerText.replace(/[^0-9]/g, ''); // Extrae solo los números
        if(textoPrecio) {
            let numero = parseInt(textoPrecio);
            // Formato de pesos colombianos
            precioEl.innerText = new Intl.NumberFormat('es-CO', {
                style: 'currency',
                currency: 'COP',
                minimumFractionDigits: 0
            }).format(numero);
        }
    });

    // 2. CONFIRMACIÓN VISUAL AL AÑADIR AL CARRITO
    // Mejora la experiencia del usuario mostrando que su acción tuvo éxito
    const botonesComprar = document.querySelectorAll('.btn-comprar');
    botonesComprar.forEach(boton => {
        boton.addEventListener('click', function(e) {
            // Si el botón es un enlace <a> y quieres redirigir, quita el e.preventDefault()
            // e.preventDefault(); 
            
            const textoOriginal = this.innerText;
            this.innerText = "¡Agregado!";
            this.style.backgroundColor = "var(--naranja-alerta)";
            
            // Restaura el botón después de 2 segundos
            setTimeout(() => {
                this.innerText = textoOriginal;
                this.style.backgroundColor = "var(--verde-claro)";
            }, 2000);
        });
    });

    // 3. DESPLAZAMIENTO SUAVE DEL MENÚ DE CATEGORÍAS (Para PC)
    // Permite usar la rueda del ratón para mover el menú horizontal de categorías
    const menuCategorias = document.querySelector('.category-menu');
    if(menuCategorias) {
        menuCategorias.addEventListener('wheel', (evt) => {
            evt.preventDefault();
            menuCategorias.scrollLeft += evt.deltaY * 2;
        });
    }
});