from fastapi import Response, status


def no_content() -> Response:
    return Response(status_code=status.HTTP_204_NO_CONTENT)
