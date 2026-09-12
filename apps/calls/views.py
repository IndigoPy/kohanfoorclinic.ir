from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import CallLogSerializer, SmsLogSerializer

class CallLogCreateView(APIView):
    def post(self, request):
        serializer = CallLogSerializer(data=request.data, many=True)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Call logs saved"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SmsLogCreateView(APIView):
    def post(self, request):
        serializer = SmsLogSerializer(data=request.data, many=True)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "SMS logs saved"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)