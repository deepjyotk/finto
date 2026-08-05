import requests
from pydantic import BaseModel, Field


class User(BaseModel):
    ID: int = Field(alias="id")
    name: str
    username: str
    email: str


def get_user(user_id: int) -> User:
    url = f"https://jsonplaceholder.typicode.com/users/{user_id}"

    response = requests.get(url)
    response.raise_for_status()

    # Bind JSON response to Python model
    content_type = response.headers.get("Content-Type", "")

    if "application/json" in content_type:
        data = response.json()
        print(type(data))
        # print("JSON response:", data)

    elif "text/html" in content_type:
        html = response.text
        print("HTML response:", html)

    elif "text/plain" in content_type:
        text = response.text
        print("Plain text response:", text)

    else:
        raw_bytes = response.content
        print("Other response type:", content_type)
        print("Raw bytes length:", len(raw_bytes))

    
    user = User(**data)

    return user


if __name__ == "__main__":
    user = get_user(1)

    print(user)
    print(user.name)
    print(user.email)