import { createRouter, createWebHistory } from 'vue-router';
import AgentList from '../views/AgentList.vue';
import AgentTest from '../views/AgentTest.vue';
import Login from '../views/Login.vue';
import Settings from '../views/Settings.vue';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: Login, meta: { public: true } },
    { path: '/', component: AgentList },
    { path: '/test', component: AgentTest },
    { path: '/settings', component: Settings },
  ],
});

router.beforeEach((to) => {
  if (!to.meta.public && !localStorage.getItem('api_key')) return '/login';
  if (to.path === '/login' && localStorage.getItem('api_key')) return '/';
});

export default router;

