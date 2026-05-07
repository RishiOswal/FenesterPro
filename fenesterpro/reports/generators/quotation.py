from django.template.loader import render_to_string

# WeasyPrint requires GTK3, moving inside function to prevent Django startup crash on Windows


def calculate_quotation_totals(project, tax_percent=18.0):
    windows = project.windows.prefetch_related('cut_pieces__profile', 'typology__hardware_rules__hardware').all()
    grand_total = 0
    items = []

    for w in windows:
        # Profile cost based on actual computed cut pieces
        profile_cost = 0.0
        for piece in w.cut_pieces.all():
            profile_cost += piece.length * piece.profile.unit_cost

        # Glass cost
        glass_cost = (w.width * w.height / 1000000) * w.glass_type.cost_per_sqm

        # Hardware cost
        hardware_cost = 0.0
        context = {
            'width': w.width,
            'height': w.height,
            'num_panels': 2 if 'sliding' in w.typology.category else 1,
        }
        if 'sliding' in w.typology.category and '3' in w.typology.code:
            context['num_panels'] = 3
            
        for hw_rule in w.typology.hardware_rules.all():
            try:
                qty = eval(hw_rule.quantity_formula, {"__builtins__": None}, context)
                hardware_cost += float(qty) * hw_rule.hardware.unit_cost
            except Exception:
                pass

        # Apply finish multiplier
        finish_multiplier = w.finish.cost_factor
        
        # Calculate unit rate and amount
        # Adding a 50% standard business markup to raw material costs so the subtotal exceeds raw material costs
        unit_rate = (profile_cost + glass_cost + hardware_cost) * finish_multiplier * 1.5
        amount = unit_rate * w.quantity
        grand_total += amount

        items.append({
            'item_code': w.item_code,
            'location': w.location_note,
            'description': f"{w.typology.name} - {w.glass_type.name} ({w.finish.name})",
            'width': w.width,
            'height': w.height,
            'qty': w.quantity,
            'unit_rate': round(unit_rate, 2),
            'amount': round(amount, 2),
        })
    subtotal = round(grand_total, 2)
    tax_amount = round(subtotal * (tax_percent / 100), 2)
    total = round(subtotal + tax_amount, 2)
    return {
        'items': items,
        'subtotal': subtotal,
        'tax_amount': tax_amount,
        'total': total,
    }


def calculate_material_cost(project, result_data):
    comp = result_data.get('comparison', {})
    
    # Use exact costs if available from newer optimisation runs
    if 'baseline_cost' in comp:
        return comp['baseline_cost'], comp['optimized_cost'], comp['cost_saved']

    # Fallback to rough average calculation for older data
    profiles_used = set()
    for w in project.windows.all():
        for piece in w.cut_pieces.all():
            profiles_used.add(piece.profile)
            
    if not profiles_used:
        return 0, 0, 0
        
    avg_unit_cost = sum(p.unit_cost for p in profiles_used) / len(profiles_used)
    bar_length = project.profile_system.standard_bar_length if project.profile_system else 6000
    avg_bar_cost = avg_unit_cost * bar_length
    
    baseline_bars = comp.get('baseline_bars_used', 0)
    optimized_bars = comp.get('optimized_bars_used', 0)
    
    cost_before = round(baseline_bars * avg_bar_cost, 2)
    cost_after = round(optimized_bars * avg_bar_cost, 2)
    savings = round(cost_before - cost_after, 2)
    
    return cost_before, cost_after, savings


def generate_quotation_pdf(request, project):
    pricing = calculate_quotation_totals(project, tax_percent=18.0)

    context = {
        'project': project,
        'items': pricing['items'],
        'subtotal': pricing['subtotal'],
        'gst': pricing['tax_amount'],
        'total': pricing['total'],
    }

    html_string = render_to_string('reports/quotation_pdf.html', context)
    try:
        from weasyprint import HTML
        return HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf()
    except OSError:
        # Fallback for Windows without GTK3
        return html_string
