from rest_framework.response import Response
from rest_framework import status


def error_response(msg,data=None,status = status.HTTP_400_BAD_REQUEST): 
    return Response([{'error':msg, 'data':data}],status=status)

def success_response(msg=None,data=None,status = status.HTTP_200_OK ):
    return Response({'msg':msg,'data':data},status=status)


def authorization_error(msg,data=None):
    return Response([{'error':msg, 'data':data}],status=status.HTTP_401_UNAUTHORIZED)

def server_error(msg,data=None):
    return Response([{'error':msg, 'data':data}],status=status.HTTP_500_INTERNAL_SERVER_ERROR)