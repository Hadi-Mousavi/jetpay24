from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from .models import Notification
from .services import count_unread_notifications
from .utils import serialize_notification


def _wants_json(request):
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return True
    accept = request.headers.get('Accept', '')
    return 'application/json' in accept


@login_required
@require_POST
def mark_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.is_read = True
    notification.save(update_fields=['is_read'])

    if _wants_json(request):
        return JsonResponse({
            'success': True,
            'unread_count': count_unread_notifications(request.user),
        })

    next_url = request.POST.get('next') or reverse('dashboard')
    return redirect(next_url)


@login_required
@require_POST
def mark_all_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)

    if _wants_json(request):
        return JsonResponse({
            'success': True,
            'unread_count': 0,
        })

    return redirect('dashboard')


@login_required
@require_GET
def dropdown_api(request):
    notifications = (
        Notification.objects
        .filter(user=request.user)
        .order_by('-created_at')[:5]
    )
    return JsonResponse({
        'unread_count': count_unread_notifications(request.user),
        'notifications': [
            serialize_notification(notification)
            for notification in notifications
        ],
    })
