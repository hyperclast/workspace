from django.shortcuts import render


def pricing(request):
    return render(request, "core/pricing.html")
