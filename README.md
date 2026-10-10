# YXI96 Mira

Punto de mira encima de la pantalla, para shooters. La mira vive en su propia ventana: siempre delante, con el fondo transparente, y el clic la atraviesa hasta el juego.

## Qué se puede ajustar

- Estilo: punto, cruz, cruz abierta, círculo, círculo y punto, cruz y círculo, marcas, cuadrado
- Tamaño
- Grosor
- Transparencia
- Color, blanco al empezar
- Contorno oscuro, para que el blanco se vea en fondos claros
- Centro horizontal y vertical, por si el juego no cae en el medio exacto de la pantalla

## Windows

Hace falta Python 3 con tcl/tk. En el instalador de python.org, deja marcada esa opción.

Doble clic en `iniciar_mira.bat`, o:

```bat
python iniciar_mira.py
```

Con el juego delante, `Ctrl+Alt+M` oculta o muestra la mira. `F8` hace lo mismo cuando el panel está enfocado.

## Linux

```bash
sudo apt install python3-tk python3-gi python3-gi-cairo gir1.2-gtk-3.0 python3-cairo
python3 iniciar_mira.py
```

## Pantalla completa

En ventana, o en ventana sin bordes, la mira queda por encima. La pantalla completa exclusiva dibuja el juego por encima de cualquier ventana y puede taparla. La mira no entra dentro del juego: solo se dibuja encima de la pantalla.
