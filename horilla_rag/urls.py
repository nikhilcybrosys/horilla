from django.urls import path

from horilla_rag import views

urlpatterns = [
    path("search/", views.rag_search, name="rag-search"),
    path("query/", views.rag_query, name="rag-query"),
    path("chat/", views.rag_chat, name="rag-chat"),
    path("status/", views.rag_status, name="rag-status"),
]
