import flet as ft
from httpx._transports import default
from src.views.theme import C


def limited_shots():
    """Função resposável por limita a quantidade de shots"""
    def validation_limite(e):

            value = e.control.value
            if value:
                if not value.isdigit() or not (1 <= int(value) <= 10):
                    e.control.error_text = "Digite um valor entre 1 e 10"
                else:
                    e.control.error_text = None
            else:
                    e.control.error_text = None

            e.control.update()

    return ft.TextField(
            value="3",
            label="Max 10",
            keyboard_type=ft.KeyboardType.NUMBER,
            border_color=C.BORDER_ACCENT,
            focused_border_color=C.ACCENT,
            input_filter=ft.InputFilter(allow=True, regex_string=r"^[0-9]*$", replacement_string=""),
            on_change=validation_limite,
            width=150,
            border_radius=8,
        ) #



