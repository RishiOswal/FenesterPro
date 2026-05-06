from django.urls import path
from . import views

app_name = 'projects'

urlpatterns = [
    path('', views.project_list, name='list'),
    path('new/', views.project_create, name='new'),
    path('<int:pk>/', views.project_detail, name='detail'),
    path('<int:pk>/add-window/', views.add_window, name='add_window'),
    path('<int:pk>/calculate/', views.calculate_project, name='calculate'),
    path('<int:pk>/optimise/', views.optimise_project, name='optimise'),
    path('<int:pk>/optimise/report/', views.optimisation_report, name='optimisation_report'),
    path('<int:pk>/accept/', views.accept_order, name='accept'),
    path('<int:pk>/reject/', views.reject_order, name='reject'),
    path('<int:pk>/invoice/', views.upsert_invoice, name='invoice'),
]
