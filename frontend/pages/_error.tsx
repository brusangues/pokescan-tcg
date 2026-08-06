// _error custom (Pages Router) — contorna o bug do _error.js interno do Next
// 15.5 no Windows (vercel/next.js#82366): useContext null durante o export.
import React from 'react';

function Error({ statusCode }: { statusCode?: number }) {
  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'sans-serif' }}>
      <div style={{ textAlign: 'center' }}>
        <h1 style={{ fontSize: '3rem', color: '#cbd5e1', margin: 0 }}>{statusCode || 500}</h1>
        <p style={{ color: '#64748b' }}>Algo deu errado.</p>
      </div>
    </div>
  );
}

Error.getInitialProps = ({ res, err }: any) => {
  const statusCode = res ? res.statusCode : err ? err.statusCode : 404;
  return { statusCode };
};

export default Error;
