import requests
from pydantic import BaseModel


class PostRequest(BaseModel):
    title: str
    body: str
    userId: int


def create_post():
    url = "https://jsonplaceholder.typicode.com/posts"

    request_body = PostRequest(
        title="My first post",
        body="This is the post content",
        userId=1
    )

    response = requests.post(
        url,
        json=request_body.model_dump()  # sends JSON body
    )

    response.raise_for_status()

    data = response.json()

    print("Status code:", response.status_code)
    print("Response JSON:", data)

    return data


if __name__ == "__main__":
    created_post = create_post()
    print(created_post)