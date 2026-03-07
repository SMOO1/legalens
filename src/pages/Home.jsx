import React from 'react';
import Layout from '../components/Layout';
import Uploader from '../components/Uploader';

export default function Home() {
    return (
        <Layout>
            <div className="h-full flex flex-col justify-center items-center py-10 md:py-20">
                <Uploader />
            </div>
        </Layout>
    );
}
