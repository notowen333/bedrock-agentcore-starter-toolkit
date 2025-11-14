"""UI components for interactive CLI selectors."""

import string
from time import sleep

from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, VSplit
from prompt_toolkit.layout.containers import Float, FloatContainer, Window
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.output import ColorDepth
from prompt_toolkit.styles import Style, StyleTransformation
from prompt_toolkit.widgets import TextArea

STYLE = Style.from_dict(
    {
        "": "nounderline",
        "title": "bold fg:#ffffff",
        "option-name": "fg:#ffffff",
        "option-desc": "fg:#777777",
    }
)


class NoUnderline(StyleTransformation):
    """Disable underline styling."""

    def transform_attrs(self, attrs):
        """Return attrs without underline."""
        return attrs._replace(underline=False)


# ---------------------------------------------------------------------------
# STATE + FRAGMENTS
# ---------------------------------------------------------------------------


class OptionState:
    """Track selector cursor and chosen value."""

    def __init__(self, values):
        """Initialize state with a list of (value, name, desc)."""
        self.values = values
        self.current = 0
        self.selected = values[0][0] if values else None

    @property
    def current_value(self):
        """Return the value at the cursor."""
        return self.values[self.current][0]


def build_option_fragments(state: OptionState):
    """Produce formatted line fragments for the option list.

    Indentation is preserved because FormattedTextControl respects literal text.
    """
    frags = []

    for idx, (val, name, desc) in enumerate(state.values):
        is_cursor = idx == state.current
        is_checked = val == state.selected

        cursor_prefix = "> " if is_cursor else "  "
        bullet = "● " if is_checked else "○ "

        frags.append(("", cursor_prefix))
        frags.append(("class:option-name", bullet + name))
        frags.append(("", "\n"))

        if desc and desc.strip():
            frags.append(("class:", "    "))
            frags.append(("class:option-desc", "    " + desc))
            frags.append(("", "\n"))

    return frags


# ---------------------------------------------------------------------------
# SELECT-ONE CONTROL
# ---------------------------------------------------------------------------


def select_one(title: str, options: dict[str, str], default: str | None = None):
    """Interactive single-choice selector."""
    values = [(val, val, desc) for val, desc in options.items()]
    state = OptionState(values)

    options_control = FormattedTextControl(
        lambda: build_option_fragments(state),
        focusable=True,
        show_cursor=False,
    )

    title_window = Window(
        FormattedTextControl([("class:title", title)], focusable=False),
        height=1,
        dont_extend_height=True,
    )

    options_window = Window(
        options_control,
        always_hide_cursor=True,
        wrap_lines=False,
    )

    kb = KeyBindings()

    @kb.add("down")
    def _(e):
        if state.current < len(state.values) - 1:
            state.current += 1
        state.selected = state.current_value
        e.app.invalidate()

    @kb.add("up")
    def _(e):
        if state.current > 0:
            state.current -= 1
        state.selected = state.current_value
        e.app.invalidate()

    @kb.add("enter")
    def _(e):
        state.selected = state.current_value
        e.app.exit(result=state.current_value)

    @kb.add("escape")
    @kb.add("c-c")
    def _(e):
        e.app.exit(result=None)

    root = HSplit(
        [
            title_window,
            Window(height=1, char=" "),
            options_window,
        ]
    )

    app = Application(
        layout=Layout(root, focused_element=options_window),
        key_bindings=kb,
        style=STYLE,
        style_transformation=NoUnderline(),
        color_depth=ColorDepth.DEPTH_24_BIT,
        erase_when_done=False,
        full_screen=False,
        mouse_support=False,
    )

    result = app.run()
    sleep(0.10)
    print()
    return result


# ---------------------------------------------------------------------------
# ASK TEXT INPUT
# ---------------------------------------------------------------------------


def ask_text(title: str, default: str | None = None, redact: bool = False) -> str | None:
    """Prompt user for a single-line text value."""
    field = TextArea(
        text=default or "",
        multiline=False,
        style="class:option-name",
        focus_on_click=True,
        wrap_lines=False,
        password=redact
    )

    kb = KeyBindings()

    @kb.add("enter")
    def _(ev):
        ev.app.exit(result=field.text.strip())

    @kb.add("escape")
    @kb.add("c-c")
    def _(ev):
        ev.app.exit(result=None)

    input_row = VSplit(
        [
            Window(FormattedTextControl([("class:option-desc", "> ")]), width=2, align="left"),
            field,
        ],
        height=1,
    )

    root = HSplit(
        [
            Window(FormattedTextControl([("class:title", title)]), height=1),
            Window(height=1, char=" "),
            input_row,
            Window(height=1, char=" "),
        ]
    )

    app = Application(
        layout=Layout(root, focused_element=field),
        key_bindings=kb,
        style=STYLE,
        style_transformation=NoUnderline(),
        erase_when_done=False,
        full_screen=False,
        color_depth=ColorDepth.DEPTH_24_BIT,
        mouse_support=False,
    )

    result = app.run()
    sleep(0.10)
    print()
    return result

# ---------------------------------------------------------------------------
# ASK CHOICE WITH AUTOCOMPLETE
# ---------------------------------------------------------------------------


def ask_choice(title: str, choices: list[str]) -> str | None:
    """Prompt user to choose from a simple inline choice list."""
    completer = WordCompleter(choices, ignore_case=True)

    buf = Buffer(
        completer=completer,
        complete_while_typing=True,
        multiline=False,
    )

    input_control = BufferControl(
        buffer=buf,
        focus_on_click=True,
    )

    kb = KeyBindings()

    @kb.add("enter")
    def _(ev):
        entered = buf.text.strip()
        for c in choices:
            if entered.lower() == c.lower():
                ev.app.exit(result=c)
                return
        buf.text = ""

    @kb.add("escape")
    @kb.add("c-c")
    def _(ev):
        ev.app.exit(result=None)

    choices_text = "  Available: " + ", ".join(choices)
    choices_window = Window(
        FormattedTextControl([("class:option-desc", choices_text)]),
        height=1,
        dont_extend_height=True,
    )

    input_row = VSplit(
        [
            Window(FormattedTextControl([("class:option-desc", "> ")]), width=2),
            Window(input_control, height=1),
        ]
    )

    root_body = HSplit(
        [
            Window(FormattedTextControl([("class:title", title)]), height=1),
            Window(height=1, char=" "),
            choices_window,
            Window(height=1, char=" "),
            input_row,
            Window(height=1, char=" "),
        ]
    )

    root = FloatContainer(
        content=root_body,
        floats=[
            Float(
                xcursor=True,
                ycursor=True,
                content=CompletionsMenu(max_height=8),
            )
        ],
    )

    app = Application(
        layout=Layout(root, focused_element=input_control),
        key_bindings=kb,
        style=STYLE,
        style_transformation=NoUnderline(),
        color_depth=ColorDepth.DEPTH_24_BIT,
        mouse_support=False,
        full_screen=False,
        erase_when_done=False,
    )

    result = app.run()
    sleep(0.1)
    print()
    return result


# ---------------------------------------------------------------------------
# WELCOME SCREEN
# ---------------------------------------------------------------------------


def show_welcome(title: str, description: list[str]) -> None:
    """Display a clean welcome screen before the questionnaire begins.

    User presses any key to continue.
    """
    kb = KeyBindings()

    for char in string.printable:

        @kb.add(char)
        def _(ev, c=char):
            ev.app.exit(result=None)

    @kb.add("enter")
    @kb.add("c-c")
    @kb.add("left")
    def _(ev):
        ev.app.exit(result=None)

    message_lines = [
        ("class:title", f"{title}\n"),
        ("", "\n"),
    ]

    for line in description:
        style = "class:option-desc" if line.strip() else ""
        message_lines.append((style, line))

    message_window = Window(
        FormattedTextControl(message_lines, focusable=True),
        always_hide_cursor=True,
    )

    root = HSplit(
        [
            Window(height=1, char=" "),
            message_window,
            Window(height=1, char=" "),
        ]
    )

    app = Application(
        layout=Layout(root, focused_element=message_window),
        key_bindings=kb,
        style=STYLE,
        style_transformation=NoUnderline(),
        color_depth=ColorDepth.DEPTH_24_BIT,
        full_screen=False,
        mouse_support=False,
        erase_when_done=False,
    )

    app.run()
    print()
