import { useRef, useState } from "react";

// Parent → Child: pass data via props
// Child → Parent: call a callback passed as a prop

type ChildProps = {
  message: string;
  parenCallback: (name: string) => void;
};

function Child({ message, parenCallback }) {
  return (
    <div>
    <h1>Child Component</h1>
      <p>"Hi" + {message}</p>
      <button type="button" onClick={() => parenCallback("Hello from child")}>
        Say hello to parent
      </button>
    </div>
  );
}


function Child2({ message, parenCallback }: ChildProps){

  return (
    <div>
      <h2>"Message From Parent:" + {message}</h2>
      <ul>
        <li>{message[0]}</li>
        <li>{message[1]}</li>
      </ul>
    </div>
  );

}


function InputFocus() {
  const inputRef = useRef(null);

  function focusInput() {
    inputRef.current.focus();
  }

  return (
    <div>
      <input ref={inputRef} placeholder="Enter name" />

      <button onClick={focusInput}>
        Focus input
      </button>
    </div>
  );
}

function Timer() {
  const timerIdRef = useRef(null);

  function startTimer() {
    timerIdRef.current = setInterval(() => {
      console.log("Timer running");
    }, 1000);
  }

  function stopTimer() {
    clearInterval(timerIdRef.current);
  }

  return (
    <div>
      <button onClick={startTimer}>Start</button>
      <button onClick={stopTimer}>Stop</button>
    </div>
  );
}

export default function ParentChildCommunication() {
  const [parentMessage, setParentMessage] = useState("Hello from parent");

  function parentCallback(message: string){
    console.log("Message From Child Component"+ message) ;

    setParentMessage(message);
  }

  return (
    <div>
      <h1>Parent Component</h1>
      <p>Parent state: {parentMessage}</p>
      <Child
        message={parentMessage}
        parenCallback={parentCallback}
      />

      <Child2
        message={parentMessage}
        parenCallback={parentCallback}
      />

    <InputFocus />

    <Timer />
    </div>
  );
}
