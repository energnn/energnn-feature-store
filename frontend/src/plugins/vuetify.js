import 'vuetify/styles';
import { createVuetify } from 'vuetify';
import * as components from 'vuetify/components';
import * as directives from 'vuetify/directives';

/**
 * Creates a configured Vuetify instance.
 * @param {{ defaultTheme?: string }} opts
 * @returns {import('vuetify').VuetifyOptions}
 */
export default function createMyVuetify({ defaultTheme = 'dark' } = {}) {
  return createVuetify({
    components,
    directives,
    theme: {
      defaultTheme,
      themes: {
        light: {
          colors: {
            background: '#FFFFFF',
            surface: '#FFFFFF',
            primary: '#1976D2',
            'primary-darken-1': '#115293',
            secondary: '#424242',
            accent: '#82B1FF',
            error: '#D32F2F',
            info: '#2196F3',
            success: '#4CAF50',
            warning: '#FB8C00',
            green: '#4CAF50',
            'on-surface': '#000000',
          }
        },
        dark: {
          colors: {
            background: '#121212',
            surface: '#1E1E1E',
            primary: '#90CAF9',
            'primary-darken-1': '#5A9BD6',
            secondary: '#B0BEC5',
            accent: '#82B1FF',
            error: '#EF9A9A',
            info: '#90CAF9',
            success: '#81C784',
            warning: '#FFB74D',
            green: '#81C784',
            'on-surface': '#FFFFFF',
          }
        }
      }
    },
  });
}
