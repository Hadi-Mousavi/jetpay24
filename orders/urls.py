from django.urls import path

from . import views

urlpatterns = [
    path('',                                        views.order_list,                    name='order_list'),
    path('create/',                                 views.order_create,                  name='order_create'),
    path('<int:pk>/',                               views.order_detail,                  name='order_detail'),
    path('<int:pk>/message/',                       views.order_send_message,            name='order_send_message'),
    path('<int:pk>/attach/',                        views.order_upload_attachment,       name='order_upload_attachment'),
    path('ajax/subcategories/',                     views.ajax_subcategories,            name='ajax_subcategories'),
    # Secure authenticated file downloads
    path('file/attachment/<int:pk>/',              views.order_attachment_download,     name='order_attachment_download'),
    path('file/message-attachment/<int:pk>/',      views.message_attachment_download,   name='message_attachment_download'),
]
