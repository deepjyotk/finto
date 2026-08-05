function debounce(func, wait) {
    let timerId = null;
  
    return function (...args) {
      const context = this;
  
      console.log("debounced function called with:", args);
  
      clearTimeout(timerId);
  
      timerId = setTimeout(() => {
        console.log("wait finished, calling actual function");
        func.apply(context, args);
      }, wait);
    };
  }
  
  // Example
  let i = 0;
  
  function increment(value) {
    i += value;
    console.log("increment ran, i =", i);
  }
  
  const debouncedIncrement = debounce(increment, 100);
  
  console.log("t = 0");
  debouncedIncrement(1);
  
  setTimeout(() => {
    console.log("t = 50");
    debouncedIncrement(2);
  }, 50);
  
  setTimeout(() => {
    console.log("t = 100");
    console.log("i is still:", i);
  }, 100);
  
  setTimeout(() => {
    console.log("t = 150");
    console.log("i is:", i);
  }, 150);
  
  setTimeout(() => {
    console.log("t = 200");
    console.log("final i is:", i);
  }, 200);