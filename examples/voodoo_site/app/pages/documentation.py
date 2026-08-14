import os
import ast
from voodoo import Div, Heading, Card, Text, Table, _
from app.layout import Layout
from voodoo.api import api

def get_project_pages():
    pages = []
    pages_dir = "app/pages"
    if os.path.exists(pages_dir):
        for filename in sorted(os.listdir(pages_dir)):
            if filename.endswith(".py") and not filename.startswith("_"):
                name = filename[:-3]
                route = "/" if name == "index" else f"/{name}"
                try:
                    filepath = os.path.join(pages_dir, filename)
                    with open(filepath, "r", encoding="utf-8") as f:
                        tree = ast.parse(f.read())
                        doc = ast.get_docstring(tree) or "No description provided."
                    pages.append([name, route, doc.split('\n')[0]])
                except Exception as e:
                    pages.append([name, route, f"Error parsing: {e}"])
    return pages

def get_project_models():
    models = []
    models_path = "app/models.py"
    if os.path.exists(models_path):
        try:
            with open(models_path, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read())
                for node in tree.body:
                    if isinstance(node, ast.ClassDef):
                        doc = ast.get_docstring(node) or "No description provided."
                        fields = [n.target.id for n in node.body if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)]
                        if fields or any(getattr(b, 'id', '') == "BaseModel" for b in node.bases):
                            models.append([node.name, ", ".join(fields) or "None", doc.split('\n')[0]])
        except Exception as e:
            pass
    return models

def get_project_workers():
    workers = []
    workers_path = "app/workers.py"
    if os.path.exists(workers_path):
        try:
            with open(workers_path, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read())
                for node in tree.body:
                    if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
                        is_worker = any(
                            (isinstance(d, ast.Call) and getattr(d.func, "id", "") == "queue") or
                            (isinstance(d, ast.Name) and d.id == "queue")
                            for d in node.decorator_list
                        )
                        if is_worker:
                            doc = ast.get_docstring(node) or "No description provided."
                            workers.append([node.name, "Background Task", doc.split('\n')[0]])
        except Exception:
            pass
    return workers

def get_api_endpoints():
    endpoints = []
    for path, methods in api.paths.items():
        for method, details in methods.items():
            endpoints.append([method.upper(), path, details.get("summary", "No description provided.")])
    return endpoints

def Section(title: str, description: str, content: Div):
    return Div(
        Heading(title, level=2, className="text-2xl font-bold mt-10 mb-2 text-[var(--color-text)] border-b border-[var(--color-border)] pb-2"),
        Div(description, className="text-[var(--color-text-muted)] mb-6"),
        content,
        className="mb-10"
    )

async def page(request):
    pages_data = get_project_pages()
    models_data = get_project_models()
    api_data = get_api_endpoints()
    workers_data = get_project_workers()

    sections = []

    if pages_data:
        sections.append(Section(
            "Application Pages", 
            "Routes and views available in this application (auto-detected from app/pages/).",
            Table(headers=["Page Name", "Route", "Description"], rows=pages_data, className="w-full text-left")
        ))
        
    if models_data:
        sections.append(Section(
            "Data Models", 
            "Database schemas and entities (auto-detected from app/models.py).",
            Table(headers=["Model", "Fields", "Description"], rows=models_data, className="w-full text-left")
        ))
        
    if api_data:
        sections.append(Section(
            "API Endpoints", 
            "REST API routes registered in the system.",
            Table(headers=["Method", "Endpoint", "Summary"], rows=api_data, className="w-full text-left")
        ))
        
    if workers_data:
        sections.append(Section(
            "Background Workers", 
            "Asynchronous tasks running in the background queue (auto-detected from app/workers.py).",
            Table(headers=["Worker Name", "Type", "Description"], rows=workers_data, className="w-full text-left")
        ))
        
    if not sections:
        sections.append(Div("No project components detected yet. Start building in the `app/` directory!", className="text-[var(--color-text-muted)] italic p-6"))

    content = Div(
        Card(
            Heading("Project Documentation", level=2, className="text-3xl font-bold mb-4 text-[var(--color-text)] tracking-tight"),
            Div("This is your living project documentation. It dynamically inspects your application's code and generates documentation for your pages, models, APIs, and background workers in real-time.", className="text-[var(--color-text-muted)] mb-6 text-lg"),
            *sections,
            className="bg-[var(--color-surface)] border-[var(--color-border)] backdrop-blur-md shadow-2xl"
        ),
        className="space-y-6 max-w-5xl mx-auto pb-20"
    )
    
    return Layout(content, title="Project Docs")