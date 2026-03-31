import { describe, it, expect } from 'vitest'
import { server } from '@/mocks/node'

describe('MSW server infrastructure', () => {
  it('server is defined', () => {
    expect(server).toBeDefined()
  })
})
