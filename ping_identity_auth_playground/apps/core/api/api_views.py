from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from ping_identity_auth_playground.support.utils import is_internet_available


@api_view(["GET"])
def health_check(request):
    if is_internet_available():
        return Response({"internetAvailable": True}, status=status.HTTP_200_OK)
    else:
        return Response({"internetAvailable": False}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
