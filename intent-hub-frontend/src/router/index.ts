import { createRouter, createWebHistory } from 'vue-router';
import Login from '../views/Login.vue';
import AgentList from '../views/AgentList.vue';
import AgentTest from '../views/AgentTest.vue';
import Diagnostics from '../views/Diagnostics.vue';
import Settings from '../views/Settings.vue';
import TenantList from '../views/admin/TenantList.vue';
import TenantDetail from '../views/admin/TenantDetail.vue';
import SkillSources from '../views/tenant/SkillSources.vue';
import SkillDrafts from '../views/tenant/SkillDrafts.vue';

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: Login,
    meta: { public: true }
  },
  {
    path: '/',
    name: 'AgentList',
    component: AgentList,
  },
  {
    path: '/test',
    name: 'AgentTest',
    component: AgentTest,
  },
  {
    path: '/diagnostics',
    name: 'Diagnostics',
    component: Diagnostics,
  },
  {
    path: '/settings',
    name: 'Settings',
    component: Settings,
  },
  {
    path: '/skills/sources',
    name: 'SkillSources',
    component: SkillSources,
  },
  {
    path: '/skills/drafts',
    name: 'SkillDrafts',
    component: SkillDrafts,
  },
  {
    path: '/admin/tenants',
    name: 'TenantList',
    component: TenantList,
  },
  {
    path: '/admin/tenants/:tenantId',
    name: 'TenantDetail',
    component: TenantDetail,
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach((to, _from, next) => {
  if (to.meta.public) {
    next();
    return;
  }

  if (to.path.startsWith('/admin/')) {
    const adminToken = localStorage.getItem('admin_token');
    if (!adminToken) {
      next({ name: 'Login' });
      return;
    }
    next();
    return;
  }

  const tenantAccessCode = localStorage.getItem('tenant_access_code');
  if (!tenantAccessCode) {
    next({ name: 'Login' });
    return;
  }

  next();
});

export default router;


