from django.shortcuts import redirect, render

from .forms import OrderForm


def order_create(request):
    if request.method == 'POST':
        form = OrderForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('order_success')
    else:
        form = OrderForm()

    return render(request, 'orders/order_create.html', {'form': form})


def order_success(request):
    return render(request, 'orders/order_success.html')
