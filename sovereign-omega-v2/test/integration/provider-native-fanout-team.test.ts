import {it} from 'vitest'
import {registerNativeFanoutTeamCases} from '../contracts/provider-native-fanout-team.cases.js'
registerNativeFanoutTeamCases((name, run) => it(name, run))
