import os
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from projects.models import Project
from projects.permissions import can_access_project, is_admin_user
from .generators.quotation import generate_quotation_pdf
from .generators.boq import generate_boq_pdf
from .generators.cutting import generate_cutting_pdf
from .generators.excel import generate_excel


@login_required
def hub(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if not can_access_project(request.user, project):
        return HttpResponse("Access denied.", status=403)
    is_admin = is_admin_user(request.user)
    return render(request, 'reports/hub.html', {'project': project, 'is_admin': is_admin})


@login_required
def quotation_report(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if not can_access_project(request.user, project):
        return HttpResponse("Access denied.", status=403)
    
    is_admin = is_admin_user(request.user)
    if not is_admin and project.status not in [Project.STATUS_ACCEPTED, Project.STATUS_IN_PRODUCTION, Project.STATUS_COMPLETED]:
        return HttpResponse("Report only available after order is accepted.", status=403)
    result = generate_quotation_pdf(request, project)
    if isinstance(result, str):
        return HttpResponse(result)
    response = HttpResponse(result, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Quotation_{project.project_code}.pdf"'
    return response


@login_required
def boq_report(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if not can_access_project(request.user, project):
        return HttpResponse("Access denied.", status=403)
    
    is_admin = is_admin_user(request.user)
    if not is_admin and project.status not in [Project.STATUS_ACCEPTED, Project.STATUS_IN_PRODUCTION, Project.STATUS_COMPLETED]:
        return HttpResponse("Report only available after order is accepted.", status=403)
    result = generate_boq_pdf(request, project)
    if isinstance(result, str):
        return HttpResponse(result)
    response = HttpResponse(result, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="BOQ_{project.project_code}.pdf"'
    return response


@login_required
def cutting_report(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if not can_access_project(request.user, project):
        return HttpResponse("Access denied.", status=403)
    if not is_admin_user(request.user):
        return HttpResponse("Access denied. Admin only.", status=403)
    result = generate_cutting_pdf(request, project)
    if isinstance(result, str):
        return HttpResponse(result)
    response = HttpResponse(result, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="BarCutting_{project.project_code}.pdf"'
    return response


@login_required
def excel_report(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if not can_access_project(request.user, project):
        return HttpResponse("Access denied.", status=403)
    if not is_admin_user(request.user):
        return HttpResponse("Access denied. Admin only.", status=403)
    workbook = generate_excel(project)
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="Project_{project.project_code}.xlsx"'
    workbook.save(response)
    return response
