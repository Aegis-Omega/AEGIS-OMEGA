import { it } from 'vitest'
import { registerFanoutCases } from '../contracts/provider-native-fanout.cases.js'
registerFanoutCases((name, test) => it(name, test))
