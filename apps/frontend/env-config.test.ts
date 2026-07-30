// @vitest-environment node

import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, describe, expect, it } from 'vitest'
import { resolveConfig, type UserConfig } from 'vite'
import viteConfig from './vite.config'

const temporaryDirectories: string[] = []

afterEach(async () => {
  await Promise.all(
    temporaryDirectories.splice(0).map((directory) => rm(directory, { force: true, recursive: true })),
  )
})

describe('repository-root Vite environment', () => {
  it('loads root VITE values and gives process values precedence', async () => {
    const repositoryRoot = await mkdtemp(join(tmpdir(), 'cockpit-vite-env-'))
    temporaryDirectories.push(repositoryRoot)
    const frontendRoot = join(repositoryRoot, 'apps', 'frontend')
    await mkdir(frontendRoot, { recursive: true })
    const mode = `issue-10-${Date.now()}`
    const variable = `VITE_ROOT_ENV_${Date.now()}`
    await writeFile(
      join(repositoryRoot, `.env.${mode}`),
      `${variable}=from-root-env\n`,
      'utf8',
    )
    const config = viteConfig as UserConfig
    const previousValue = process.env[variable]

    try {
      delete process.env[variable]
      const fromFile = await resolveConfig({ ...config, root: frontendRoot }, 'build', mode)
      expect(config.envDir).toBe('../..')
      expect(fromFile.env[variable]).toBe('from-root-env')

      process.env[variable] = 'from-process-env'
      const fromProcess = await resolveConfig({ ...config, root: frontendRoot }, 'build', mode)
      expect(fromProcess.env[variable]).toBe('from-process-env')
    } finally {
      if (previousValue === undefined) delete process.env[variable]
      else process.env[variable] = previousValue
    }
  })
})
