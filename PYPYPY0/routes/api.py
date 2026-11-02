from flask import Blueprint, jsonify, request

from core.controller import MacroController

api = Blueprint("api", __name__, url_prefix="/api")
controller = MacroController()


def payload():
    return request.get_json(silent=True) or {}


def result(success=True, **extra):
    return jsonify({"success": success, **controller.snapshot(), **extra})


@api.errorhandler(ValueError)
@api.errorhandler(FileNotFoundError)
@api.errorhandler(RuntimeError)
def handled_error(error):
    return result(False, error=str(error)), 400


@api.post("/record")
def record():
    return result(controller.start_record())


@api.post("/record/pause")
def pause_record():
    return result(controller.pause_record())


@api.post("/record/resume")
def resume_record():
    return result(controller.resume_record())


@api.post("/stop")
def stop():
    return result(controller.stop_all())


@api.post("/play")
def play():
    data = payload()
    return result(controller.play(data.get("speed"), data.get("loop")))


@api.post("/playback-settings")
def playback_settings():
    data = payload()
    controller.set_playback_options(data.get("speed", 1), data.get("loop", 1))
    return result(True)


@api.post("/pause")
def pause():
    return result(controller.pause())


@api.post("/resume")
def resume():
    return result(controller.resume())


@api.post("/pause-resume")
def pause_resume():
    return result(controller.toggle_play_pause())


@api.post("/autoclicker/start")
def autoclicker_start():
    data = payload()
    return result(controller.start_autoclicker(
        interval=data.get("interval", 0.1), count=data.get("count", 0),
        button=data.get("button", "left"), jitter=data.get("jitter", 0),
    ))


@api.post("/autoclicker/stop")
def autoclicker_stop():
    return result(controller.stop_autoclicker())


@api.post("/shutdown-mode")
def shutdown_mode():
    controller.toggle_shutdown_mode()
    return result(True)


@api.post("/cancel-shutdown")
def cancel_shutdown():
    return result(controller.cancel_shutdown())


@api.get("/status")
def status():
    return jsonify(controller.snapshot())


@api.get("/events")
def events():
    events = controller.get_events()
    try:
        limit = max(1, min(1000, int(request.args.get("limit", 1000))))
    except ValueError:
        limit = 1000
    return jsonify({"events": events[-limit:], "event_count": controller.recorder.get_event_count()})


@api.post("/save")
def save():
    filename = payload().get("filename", "")
    if not filename:
        raise ValueError("Nama macro wajib diisi.")
    return result(True, message="Macro berhasil disimpan", path=controller.save(filename))


@api.post("/load")
def load():
    filename = payload().get("filename", "")
    if not filename:
        raise ValueError("Pilih macro yang akan dimuat.")
    document = controller.load(filename)
    return result(True, macro=document)


@api.delete("/macros/<path:filename>")
def delete_macro(filename):
    deleted = controller.delete_macro(filename)
    return result(deleted, message="Macro dihapus" if deleted else "Macro tidak ditemukan")


@api.get("/macros")
def macros():
    return jsonify({"macros": controller.get_macro_list()})
