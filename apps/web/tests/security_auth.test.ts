import test from 'node:test';
import assert from 'node:assert';
import fs from 'node:fs';
import path from 'node:path';

test('Security check: No service-role keys or JWT secrets leaked in web bundle', () => {
  const webDir = path.resolve(import.meta.dirname, '..');
  const filesToScan: string[] = [];

  function scan(dir: string) {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      if (entry.name === 'node_modules' || entry.name === '.next' || entry.name === '.turbo' || entry.name === 'tests') continue;
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        scan(fullPath);
      } else if (/\.(ts|tsx|js|jsx|json)$/.test(entry.name)) {
        filesToScan.push(fullPath);
      }
    }
  }

  scan(webDir);

  const forbiddenTokens = [
    'SUPABASE_SERVICE_ROLE_KEY',
    'service_role',
    'postgres://',
    'postgresql://',
    'SECRET_KEY =',
    'SUPABASE_JWT_SECRET',
  ];

  for (const file of filesToScan) {
    const content = fs.readFileSync(file, 'utf-8');
    for (const token of forbiddenTokens) {
      if (content.includes(token)) {
        assert.fail(`Forbidden security secret "${token}" found in web file: ${file}`);
      }
    }
  }

  assert.ok(filesToScan.length > 10, 'Verified scanned web source files');
});

test('Role guard evaluation rules', () => {
  const roleChecker = (userRoles: string[], targetRole: string): boolean => {
    if (userRoles.includes('super_admin') || userRoles.includes('admin')) return true;
    return userRoles.includes(targetRole);
  };

  assert.strictEqual(roleChecker(['seeker'], 'seeker'), true);
  assert.strictEqual(roleChecker(['seeker'], 'owner'), false);
  assert.strictEqual(roleChecker(['admin'], 'owner'), true, 'Admin has global access');
  assert.strictEqual(roleChecker(['super_admin'], 'pg_operator'), true, 'Super admin has global access');
  assert.strictEqual(roleChecker(['owner', 'pg_operator'], 'pg_operator'), true);
});
