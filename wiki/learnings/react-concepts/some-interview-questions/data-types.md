```javascript
console.log(typeof "hello");     // string
console.log(typeof 123);         // number
console.log(typeof true);        // boolean
console.log(typeof undefined);   // undefined
console.log(typeof 10n);         // bigint
console.log(typeof Symbol());    // symbol

console.log(typeof null);        // object  // weird JS behavior
console.log(typeof {});          // object
console.log(typeof []);          // object
console.log(typeof function(){}); // function
```