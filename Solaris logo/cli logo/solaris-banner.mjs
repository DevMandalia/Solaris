// Solaris CLI banner (10G)
const c = { gold: '\x1b[38;5;221m', ember: '\x1b[38;5;209m', muted: '\x1b[38;5;138m', bone: '\x1b[38;5;250m', r: '\x1b[0m' };

export function banner(version = '1.0.0') {
  return [
    `  ${c.gold}(*) solaris${c.r}  ${c.muted}v${version}${c.r}`,
    `  ${c.ember}>${c.r} ${c.bone}solaris init --star polaris${c.r}`,
  ].join('\n');
}
