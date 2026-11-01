from django.urls import path
from .views import signup, user_login, user_logout, my_orders, track_order, home, add_to_cart, cart, update_cart, remove_from_cart, checkout, order_success

urlpatterns = [
    path('signup/', signup, name='signup'),
    path('login/', user_login, name='login'),
    path('logout/', user_logout, name='logout'),
    path('my-orders/', my_orders, name='my_orders'),
    path('', home, name='home'),
    path('add-to-cart/<int:product_id>/', add_to_cart, name='add_to_cart'),
    path('cart/', cart, name='cart'),
    path('cart/<int:product_id>/<str:action>/', update_cart, name='update_cart'),
    path('cart/remove/<int:product_id>/', remove_from_cart, name='remove_from_cart'),
    path('checkout/', checkout, name='checkout'),
    path('track-order/', track_order, name='track_order'),
    path('order-success/<int:order_id>/', order_success, name='order_success'),
]
