import uuid
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.utils import timezone
from .models import Project
from .forms import ProjectForm, CustomerProjectForm, WindowEntryForm, InvoiceForm
from calculator.engine import WindowCalculator
from optimizer.engine import BarOptimiser
from optimizer.models import OptimisationResult
from .permissions import is_admin_user, can_access_project
from reports.generators.quotation import calculate_quotation_totals


@login_required
def project_list(request):
    if is_admin_user(request.user):
        projects = Project.objects.select_related('customer', 'profile_system').all().order_by('-created_at')
    else:
        projects = Project.objects.select_related('customer', 'profile_system').filter(customer=request.user).order_by('-created_at')
    return render(request, 'projects/project_list.html', {'projects': projects, 'is_admin': is_admin_user(request.user)})


@login_required
def project_create(request):
    admin_user = is_admin_user(request.user)
    form_class = ProjectForm if admin_user else CustomerProjectForm

    if request.method == 'POST':
        form = form_class(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            # Generate a simple unique project code
            project.project_code = f"PRJ-{str(uuid.uuid4())[:8].upper()}"
            project.customer = request.user
            if not admin_user:
                project.status = Project.STATUS_PENDING
            project.save()
            messages.success(request, f"Order request {project.project_code} created successfully.")
            return redirect('projects:detail', pk=project.pk)
    else:
        form = form_class()
    return render(request, 'projects/project_form.html', {'form': form, 'is_admin': admin_user})


@login_required
def project_detail(request, pk):
    project = get_object_or_404(Project.objects.select_related('customer', 'invoice'), pk=pk)
    if not can_access_project(request.user, project):
        return HttpResponseForbidden("You do not have permission to access this order.")

    windows = project.windows.all()

    # Check if calculation and optimisation are done
    calculated_count = windows.filter(computed=True).count()
    all_calculated = windows.count() > 0 and calculated_count == windows.count()
    optimised = hasattr(project, 'optimisation_result')
    is_admin = is_admin_user(request.user)

    invoice_form = None
    auto_pricing = calculate_quotation_totals(project, tax_percent=18.0)
    invoice_tax_percent = 18.0
    if getattr(project, 'invoice', None):
        invoice_tax_percent = project.invoice.tax_percent

    if is_admin:
        invoice = getattr(project, 'invoice', None)
        invoice_form = InvoiceForm(instance=invoice)

    context = {
        'project': project,
        'windows': windows,
        'all_calculated': all_calculated,
        'optimised': optimised,
        'is_admin': is_admin,
        'invoice': getattr(project, 'invoice', None),
        'invoice_form': invoice_form,
        'auto_subtotal': auto_pricing['subtotal'],
        'auto_tax_preview': round(auto_pricing['subtotal'] * (invoice_tax_percent / 100), 2),
        'auto_total_preview': round(auto_pricing['subtotal'] + (auto_pricing['subtotal'] * (invoice_tax_percent / 100)), 2),
    }
    return render(request, 'projects/project_detail.html', context)


@login_required
def add_window(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if not can_access_project(request.user, project):
        return HttpResponseForbidden("You do not have permission to edit this order.")
    if is_admin_user(request.user):
        messages.warning(request, "Admins should review requests. Window updates are customer-owned.")
        return redirect('projects:detail', pk=project.pk)
    if project.status not in [Project.STATUS_PENDING, Project.STATUS_REJECTED]:
        messages.warning(request, "You can edit openings only while the request is pending or rejected.")
        return redirect('projects:detail', pk=project.pk)

    if request.method == 'POST':
        form = WindowEntryForm(request.POST)
        if form.is_valid():
            window = form.save(commit=False)
            window.project = project
            window.save()
            messages.success(request, "Window added successfully.")
            return redirect('projects:detail', pk=project.pk)
    else:
        # Default item code logic
        next_code = f"W{project.windows.count() + 1:02d}"
        form = WindowEntryForm(initial={'item_code': next_code})
    return render(request, 'projects/window_form.html', {'form': form, 'project': project})


@login_required
def calculate_project(request, pk):
    if request.method == 'POST':
        project = get_object_or_404(Project, pk=pk)
        if not can_access_project(request.user, project):
            return HttpResponseForbidden("You do not have permission to calculate this order.")

        calculator = WindowCalculator()

        success_count = 0
        errors = []
        for window in project.windows.filter(computed=False):
            success, msg = calculator.calculate(window)
            if success:
                success_count += 1
            else:
                errors.append(f"{window.item_code}: {msg}")
                
        if errors:
            for error in errors:
                messages.error(request, error)
        if success_count > 0:
            messages.success(request, f"Successfully calculated {success_count} windows.")

    return redirect('projects:detail', pk=pk)


import json

@login_required
def optimisation_report(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if not can_access_project(request.user, project):
        return HttpResponseForbidden("You do not have permission to access this.")
    if not is_admin_user(request.user):
        return HttpResponseForbidden("Only admins can view the optimization report.")
        
    result = getattr(project, 'optimisation_result', None)
    if not result:
        messages.error(request, "No optimization result found. Please run optimization first.")
        return redirect('projects:detail', pk=pk)
        
    return render(request, 'projects/optimisation_report.html', {
        'project': project, 
        'result_json': result.result_data,
        'result': result
    })


@login_required
def optimise_project(request, pk):
    if request.method == 'POST':
        project = get_object_or_404(Project, pk=pk)
        if not can_access_project(request.user, project):
            return HttpResponseForbidden("You do not have permission to optimize this order.")

        # Gather all computed cut pieces. We prepare both:
        # 1) strict profile-code packing baseline
        # 2) grouped packing (interchangeable profiles) for actual optimization
        strict_cut_pieces = []
        grouped_cut_pieces = []

        def _group_label(profile):
            if not profile.optimisation_group:
                return profile.name
            return f"{profile.get_role_display()} Group ({profile.optimisation_group})"

        for window in project.windows.filter(computed=True):
            for piece in window.cut_pieces.select_related('profile'):
                effective_qty = piece.quantity * window.quantity
                strict_cut_pieces.append({
                    'profile_code': piece.profile.code,
                    'profile_name': piece.profile.name,
                    'piece_name': f"{window.item_code} - {piece.piece_name}",
                    'length': piece.length,
                    'qty': effective_qty,
                })

                grouped_profile_code = (piece.profile.optimisation_group or piece.profile.code).strip()
                grouped_cut_pieces.append({
                    'profile_code': grouped_profile_code,
                    'profile_name': _group_label(piece.profile),
                    'piece_name': f"{window.item_code} - {piece.piece_name} [{piece.profile.code}]",
                    'length': piece.length,
                    'qty': effective_qty,
                })

        if not grouped_cut_pieces:
            messages.warning(request, "No calculated cut pieces found for optimisation.")
            return redirect('projects:detail', pk=pk)

        optimiser = BarOptimiser(bar_length=project.profile_system.standard_bar_length if project.profile_system else 6000)
        baseline_data = optimiser.optimise(strict_cut_pieces)
        result_data = optimiser.optimise(grouped_cut_pieces)
        result_data['comparison'] = {
            'baseline_bars_used': baseline_data.get('bars_used', 0),
            'baseline_waste_mm': baseline_data.get('waste_mm', 0.0),
            'baseline_waste_percent': baseline_data.get('waste_percent', 0.0),
            'optimized_bars_used': result_data.get('bars_used', 0),
            'optimized_waste_mm': result_data.get('waste_mm', 0.0),
            'optimized_waste_percent': result_data.get('waste_percent', 0.0),
            'bars_saved': baseline_data.get('bars_used', 0) - result_data.get('bars_used', 0),
            'waste_saved_mm': baseline_data.get('waste_mm', 0.0) - result_data.get('waste_mm', 0.0),
        }

        # Save result
        OptimisationResult.objects.update_or_create(
            project=project,
            defaults={
                'total_bars_used': result_data.get('bars_used', 0),
                'total_waste_mm': result_data.get('waste_mm', 0.0),
                'overall_efficiency': 100.0 - result_data.get('waste_percent', 0.0), # Inverse
                'result_data': result_data,
            },
        )
        comp = result_data['comparison']
        messages.success(
            request,
            f"Bar optimisation complete. Saved {comp['bars_saved']} bars and {comp['waste_saved_mm']:.1f}mm waste vs strict profile-code packing."
        )
        # Redirect to the report/animation page instead of detail
        return redirect('projects:optimisation_report', pk=pk)
    return redirect('projects:detail', pk=pk)


@login_required
def accept_order(request, pk):
    if request.method != 'POST':
        return redirect('projects:detail', pk=pk)
    if not is_admin_user(request.user):
        return HttpResponseForbidden("Only admins can accept orders.")

    project = get_object_or_404(Project, pk=pk)
    project.status = Project.STATUS_ACCEPTED
    project.accepted_by = request.user
    project.accepted_at = timezone.now()
    project.rejected_reason = ""
    project.save(update_fields=['status', 'accepted_by', 'accepted_at', 'rejected_reason'])
    messages.success(request, f"Order {project.project_code} accepted.")
    return redirect('projects:detail', pk=pk)


@login_required
def reject_order(request, pk):
    if request.method != 'POST':
        return redirect('projects:detail', pk=pk)
    if not is_admin_user(request.user):
        return HttpResponseForbidden("Only admins can reject orders.")

    project = get_object_or_404(Project, pk=pk)
    reason = request.POST.get('rejected_reason', '').strip()
    if not reason:
        messages.error(request, "Rejection reason is required.")
        return redirect('projects:detail', pk=pk)

    project.status = Project.STATUS_REJECTED
    project.rejected_reason = reason
    project.accepted_by = None
    project.accepted_at = None
    project.save(update_fields=['status', 'rejected_reason', 'accepted_by', 'accepted_at'])
    messages.success(request, f"Order {project.project_code} rejected.")
    return redirect('projects:detail', pk=pk)


@login_required
def upsert_invoice(request, pk):
    if request.method != 'POST':
        return redirect('projects:detail', pk=pk)
    if not is_admin_user(request.user):
        return HttpResponseForbidden("Only admins can manage billing.")

    project = get_object_or_404(Project, pk=pk)
    invoice = getattr(project, 'invoice', None)
    form = InvoiceForm(request.POST, instance=invoice)
    if form.is_valid():
        pricing = calculate_quotation_totals(project, tax_percent=18.0)
        invoice = form.save(commit=False)
        invoice.project = project
        invoice.subtotal = pricing['subtotal']
        invoice.tax_amount = round(invoice.subtotal * (invoice.tax_percent / 100), 2)
        invoice.total = round(invoice.subtotal + invoice.tax_amount, 2)
        invoice.generated_by = request.user
        invoice.save()
        messages.success(request, f"Invoice saved for {project.project_code}.")
    else:
        messages.error(request, "Invoice data is invalid. Please review fields.")
    return redirect('projects:detail', pk=pk)
