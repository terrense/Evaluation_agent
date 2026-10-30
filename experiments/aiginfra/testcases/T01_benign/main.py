"""正常的预约工具，无任何高危操作。"""

def book_appointment(name, department):
    return {"status": "ok", "patient": name, "department": department}
