/**
 * map & reduce on arrays (TypeScript / JavaScript)
 *
 * map    — transform EVERY item → new array (same length)
 * reduce — fold ALL items into ONE value (number, object, array, etc.)
 *
 * Think: map = "change each", reduce = "summarize all"
 */

const numbers = [1, 2, 3, 4];

// --- map ---
// Signature: array.map((item, index?, array?) => newItem)
const doubled = numbers.map((n) => n * 2);
// [2, 4, 6, 8] — same length as input

const labels = numbers.map((n) => `num-${n}`);
// ["num-1", "num-2", ...]

// --- reduce ---
// Signature: array.reduce((accumulator, item, index?, array?) => nextAccumulator, initialValue?)
const sum = numbers.reduce((acc, n) => acc + n, 0);
// 10 — 0 is the starting accumulator

const product = numbers.reduce((acc, n) => acc * n, 1);
// 24 — start at 1 so multiply works

// Without initial value, reduce uses the FIRST element as acc (risky on empty arrays)
const max = numbers.reduce((acc, n) => (n > acc ? n : acc));
// 4

// --- chaining (very common in interviews) ---
const totalOfDoubled = numbers
  .map((n) => n * 2) // [2, 4, 6, 8]
  .reduce((acc, n) => acc + n, 0); // 20

// --- reduce to build objects (groupBy pattern) ---
type User = { id: number; role: "admin" | "user" };
const users: User[] = [
  { id: 1, role: "admin" },
  { id: 2, role: "user" },
  { id: 3, role: "user" },
];

const byRole = users.reduce<Record<string, User[]>>((acc, user) => {
  const key = user.role;
  if (!acc[key]) acc[key] = [];
  acc[key].push(user);
  return acc;
}, {});
// { admin: [...], user: [...] }

// --- TypeScript: explicit callback types (optional but clear) ---
const squared: number[] = numbers.map((n: number): number => n ** 2);

const count = ["a", "bb", "ccc"].reduce<number>(
  (acc, str) => acc + str.length,
  0,
);
// 6

// Quick reference:
// | method  | returns        | mutates original? |
// |---------|----------------|-------------------|
// | map     | new array      | no                |
// | reduce  | single value   | no                |

export { doubled, sum, totalOfDoubled, byRole, squared, count };


console.log("doubled", doubled);
console.log("sum", sum);
console.log("totalOfDoubled", totalOfDoubled);
console.log("byRole", byRole);
console.log("squared", squared);
console.log("count", count);