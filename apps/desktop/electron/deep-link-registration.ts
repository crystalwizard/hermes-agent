/**
 * Whether this process should register itself as the OS handler for the
 * hermes:// scheme at startup.
 *
 * Default is true (unchanged upstream behavior). An instance that must not take
 * over the scheme from another Hermes install (e.g. a second, separately owned
 * install on the same Windows user) sets HERMES_DESKTOP_SKIP_PROTOCOL_REGISTRATION=1.
 */
export function shouldRegisterDeepLinkProtocol(env: Record<string, string | undefined>): boolean {
  return env.HERMES_DESKTOP_SKIP_PROTOCOL_REGISTRATION !== '1'
}
