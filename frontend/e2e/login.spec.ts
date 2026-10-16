import { test, expect } from '@playwright/test';

/**
 * E2E de navegação — Tela de Login (auth stub v1).
 * Prova: render fiel ao mockup, validação bloqueia submit vazio,
 * login válido navega para /overview e persiste no localStorage,
 * redirect de /login -> /overview quando já autenticado.
 */
test.describe('Login', () => {
  test.beforeEach(async ({ page }) => {
    // Estado limpo: sem auth residual.
    await page.goto('/login');
    await page.evaluate(() => localStorage.clear());
    await page.goto('/login');
  });

  test('renderiza a tela de login com a identidade Orc[hestrator]', async ({ page }) => {
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByRole('heading', { level: 1 })).toContainText('Orc');
    await expect(page.getByRole('heading', { level: 1 })).toContainText('hestrator');
    await expect(page.getByRole('textbox', { name: 'Usuário' })).toBeVisible();
    await expect(page.getByRole('textbox', { name: 'Senha' })).toBeVisible();
    await expect(page.getByRole('button', { name: /Entrar/ }).first()).toBeVisible();
  });

  test('submit vazio é bloqueado com mensagem de validação', async ({ page }) => {
    await page.getByRole('button', { name: /Entrar/ }).first().click();
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByRole('alert')).toBeVisible();
  });

  test('login válido navega para /overview e persiste a sessão', async ({ page }) => {
    await page.getByRole('textbox', { name: 'Usuário' }).fill('claudio.gerente');
    await page.getByRole('textbox', { name: 'Senha' }).fill('secret123');
    await page.getByRole('button', { name: /Entrar/ }).first().click();
    await expect(page).toHaveURL(/\/overview$/);
    const auth = await page.evaluate(() => localStorage.getItem('orc_auth'));
    expect(auth).toBe('1');
  });

  test('redireciona /login -> /overview quando já autenticado', async ({ page }) => {
    await page.evaluate(() => localStorage.setItem('orc_auth', '1'));
    await page.goto('/login');
    await expect(page).toHaveURL(/\/overview$/);
  });
});
