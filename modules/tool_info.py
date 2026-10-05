"""Vorhandene Checkweb-Werkzeuge als lesende, scrollbare Infoübersicht."""
import threading
from gi.repository import Gtk,GLib
from .model import tools_available
from .windows import center_after_map


def show_tool_info(owner):
    for window in owner.dialogs:
        if hasattr(window,'tool_results') and window.get_visible():window.present();return window
    window=owner.bind_translation(Gtk.Window(title=owner.tr('menu_info'),transient_for=owner,default_width=620,default_height=480),'title','menu_info')
    owner.dialogs.append(window)
    box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12,margin_top=16,margin_bottom=16,margin_start=16,margin_end=16);window.set_child(box)
    heading=Gtk.Box(spacing=10);heading.append(Gtk.Image.new_from_icon_name('dialog-information-symbolic'));heading.append(owner.translated_label('tools_title',xalign=0));box.append(heading)
    content=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=14)
    scroll=Gtk.ScrolledWindow(vexpand=True);scroll.set_child(content);box.append(scroll)
    content.append(owner.translated_label('tools_loading',xalign=0))
    def close(*_):
        if window in owner.dialogs:owner.dialogs.remove(window)
        window.destroy()
    box.append(owner.button('close',close))
    window.connect('close-request',lambda *_:(close(),True)[1])
    window.tool_results=None
    def render(results):
        if owner._closed or window not in owner.dialogs:return False
        child=content.get_first_child()
        while child:
            following=child.get_next_sibling();content.remove(child);child=following
        for tool in results:
            row=Gtk.Box(spacing=10)
            icon=Gtk.Image.new_from_icon_name('emblem-ok-symbolic' if tool['available'] else 'dialog-warning-symbolic');icon.set_valign(Gtk.Align.START);row.append(icon)
            details=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=3,hexpand=True)
            details.append(Gtk.Label(label=tool['name']+' — '+owner.tr('available' if tool['available'] else 'unavailable'),xalign=0,wrap=True))
            if tool['version']:details.append(Gtk.Label(label=tool['version'],xalign=0,wrap=True,selectable=True))
            details.append(Gtk.Label(label='APT: '+tool['package'],xalign=0,wrap=True,selectable=True))
            row.append(details);content.append(row)
        window.tool_results=results;window.refresh_info=lambda:render(results)
        return False
    threading.Thread(target=lambda:GLib.idle_add(render,tools_available()),daemon=True).start()
    window.connect('map',lambda *_:center_after_map(window,owner));window.present();return window
