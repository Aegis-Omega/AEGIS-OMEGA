#!/usr/bin/env node
// AEGIS Brainfuck interpreter — reads .bf file, strips comments, executes
const fs = require('fs')
const src = process.argv[2] ? fs.readFileSync(process.argv[2], 'utf8') : ''
const prog = src.replace(/[^><+\-.,[\]]/g, '')

const cells = new Uint8Array(30000)
let dp = 0, ip = 0
const jumps = {}
const stack = []
for (let i = 0; i < prog.length; i++) {
  if (prog[i] === '[') stack.push(i)
  if (prog[i] === ']') { const j = stack.pop(); jumps[j] = i; jumps[i] = j }
}
while (ip < prog.length) {
  const c = prog[ip]
  if (c === '>') dp++
  else if (c === '<') dp--
  else if (c === '+') cells[dp]++
  else if (c === '-') cells[dp]--
  else if (c === '.') process.stdout.write(String.fromCharCode(cells[dp]))
  else if (c === '[') { if (!cells[dp]) ip = jumps[ip] }
  else if (c === ']') { if (cells[dp]) ip = jumps[ip] }
  ip++
}
